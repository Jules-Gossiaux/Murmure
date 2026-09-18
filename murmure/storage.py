from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path

from .models import MODEL_BY_NAME

log = logging.getLogger(__name__)


def data_directory() -> Path:
    path = Path(os.environ.get("MURMURE_DATA_DIR") or Path(os.environ["LOCALAPPDATA"]) / "Murmure")
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Settings:
    model: str = "base"
    correction: bool = False
    language: str = "fr"
    microphone: str = ""
    hotkey_mods: int = 2
    hotkey_vk: int = 32
    hotkey_label: str = "Ctrl+Space"
    sounds: bool = False
    close_to_tray: bool = True
    startup: bool = False
    vocabulary: str = ""
    theme: str = "light"
    history_folder: str = ""
    models_folder: str = ""

    @classmethod
    def load(cls, directory: Path) -> Settings:
        path = directory / "settings.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            default = cls()
            clean = {
                f.name: data[f.name]
                for f in fields(cls)
                if f.name in data and type(data[f.name]) is type(getattr(default, f.name))
            }
            result = cls(**clean)
            if result.model not in MODEL_BY_NAME:
                result.model = "base"
            if result.language not in {"fr", "en", "auto", "de", "es", "it", "nl", "pt"}:
                result.language = "fr"
            if result.theme not in {"light", "dark"}:
                result.theme = "light"
            if not 0 <= result.hotkey_mods <= 15 or not 1 <= result.hotkey_vk <= 254:
                result.hotkey_mods, result.hotkey_vk, result.hotkey_label = 2, 32, "Ctrl+Space"
            return result
        except (OSError, ValueError, TypeError):
            log.exception("Configuration illisible, copie conservée")
            path.replace(directory / f"settings.invalid-{uuid.uuid4().hex[:8]}.json")
            return cls()

    def save(self, directory: Path) -> None:
        path = directory / "settings.json"
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(asdict(self), file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)


class History:
    def __init__(self, directory: Path, audio_directory: Path | None = None):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.audio_dir = audio_directory or self.directory / "pending"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(directory / "history.sqlite3", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.create_function("casefold", 1, str.casefold, deterministic=True)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY, created TEXT NOT NULL, duration REAL NOT NULL DEFAULT 0,
                text TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
                audio TEXT NOT NULL DEFAULT '', sample_rate INTEGER NOT NULL DEFAULT 16000
            );
            CREATE INDEX IF NOT EXISTS entries_created ON entries(created DESC);
        """)
        self.db.commit()

    def relocate(self, directory: Path, commit_settings) -> None:
        """Copy a consistent DB, commit its location, then retire the original.

        Call only when the controller is idle. Audio paths stay valid and audio does not move.
        A failed copy or settings write leaves the original database active.
        """
        destination = directory.resolve()
        with self.lock:
            if destination == self.directory:
                commit_settings()
                return
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / "history.sqlite3"
            if target.exists():
                raise FileExistsError(
                    "Ce dossier contient déjà un historique Murmure. Choisissez un autre dossier pour ne pas l’écraser."
                )
            temporary = destination / f".murmure-{uuid.uuid4().hex}.sqlite3"
            candidate = None
            installed = False
            try:
                backup = sqlite3.connect(temporary)
                try:
                    self.db.backup(backup)
                    if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise sqlite3.DatabaseError("La vérification de l’historique copié a échoué.")
                finally:
                    backup.close()
                # Windows rename refuses an existing destination, including a race with another instance.
                temporary.rename(target)
                installed = True
                candidate = History(destination, audio_directory=self.audio_dir)
                commit_settings()
            except Exception:
                if candidate:
                    candidate.close()
                temporary.unlink(missing_ok=True)
                if installed:
                    target.unlink(missing_ok=True)
                raise
            previous_db, previous_path = self.db, self.directory / "history.sqlite3"
            self.db, self.directory = candidate.db, destination
            previous_db.close()
            try:
                previous_path.unlink()
            except OSError:
                log.warning(
                    "Historique déplacé, mais ancienne copie impossible à supprimer : %s",
                    previous_path,
                    exc_info=True,
                )

    def edit_text(self, identifier: str, text: str) -> None:
        with self.lock, self.db:
            self.db.execute("UPDATE entries SET text=? WHERE id=?", (text, identifier))

    def begin(self) -> tuple[str, Path]:
        identifier = uuid.uuid4().hex
        path = self.audio_dir / f"{identifier}.pcm"
        # Journal before opening the microphone: a crash cannot orphan a recording.
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO entries(id, created, status, audio) VALUES (?, ?, ?, ?)",
                (identifier, datetime.now().astimezone().isoformat(), "pending", str(path)),
            )
        return identifier, path

    def update(self, identifier: str, **values) -> None:
        allowed = {"duration", "text", "status", "detail", "audio", "sample_rate"}
        if not values or not values.keys() <= allowed:
            raise ValueError("Invalid history columns")
        with self.lock, self.db:
            self.db.execute(
                f"UPDATE entries SET {', '.join(k + '=?' for k in values)} WHERE id=?",
                (*values.values(), identifier),
            )

    def rows(self, query: str = "", limit: int = 300) -> list[dict]:
        with self.lock:
            return [
                dict(row)
                for row in self.db.execute(
                    "SELECT * FROM entries WHERE instr(casefold(text), casefold(?)) > 0 "
                    "OR (text='' AND ?='') ORDER BY created DESC LIMIT ?",
                    (query, query, limit),
                )
            ]

    def recoverable(self) -> list[dict]:
        with self.lock:
            return [
                dict(row)
                for row in self.db.execute(
                    "SELECT * FROM entries WHERE audio != '' AND text='' ORDER BY created"
                )
            ]

    def release_audio(self, identifier: str) -> None:
        with self.lock:
            row = self.db.execute("SELECT audio FROM entries WHERE id=?", (identifier,)).fetchone()
            if row and row["audio"]:
                path = Path(row["audio"])
                if path.resolve().parent == self.audio_dir.resolve():
                    path.unlink(missing_ok=True)
                self.update(identifier, audio="")

    def delete(self, identifier: str) -> None:
        with self.lock, self.db:
            self.release_audio(identifier)
            self.db.execute("DELETE FROM entries WHERE id=?", (identifier,))

    def clear(self) -> None:
        with self.lock:
            ids = [row[0] for row in self.db.execute("SELECT id FROM entries")]
            for identifier in ids:
                self.delete(identifier)

    def close(self) -> None:
        with self.lock:
            self.db.close()
