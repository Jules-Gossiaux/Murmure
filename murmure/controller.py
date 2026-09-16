from __future__ import annotations

import logging
import sqlite3
import time
import winsound
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .audio import Recorder
from .engine import Engine
from .storage import History, Settings
from .windows import Target, foreground, insert_text

log = logging.getLogger(__name__)


class State(str, Enum):
    LOADING = "loading"
    IDLE = "idle"
    STARTING = "starting"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    INSERTING = "inserting"
    CANCELLING = "cancelling"
    ERROR = "error"
    CLOSING = "closing"


class Controller(QObject):
    changed = Signal(str, str)
    history_changed = Signal()
    notice = Signal(str, bool)
    ready_to_quit = Signal()
    event = Signal(str, object)

    def __init__(self, directory: Path, settings: Settings, history: History):
        super().__init__()
        self.directory, self.settings, self.history = directory, settings, history
        self.engine = Engine(directory)
        self.engine_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")
        self.io_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="audio-input")
        self.state = State.LOADING
        self.message = "Préparation du moteur…"
        self.recorder: Recorder | None = None
        self.record_started = 0.0
        self.target: Target | None = None
        self.job = ""
        self.path = Path()
        self.pending_tasks = 0
        self.closing = False
        self.closed = False
        self.cancelled = False
        self.transcription_started = 0.0
        self.transcription_seconds = 0.0
        self.event.connect(self._event)

    def _state(self, state: State, message: str):
        self.state, self.message = state, message
        self.changed.emit(state.value, message)

    def _submit(self, pool, kind, function):
        self.pending_tasks += 1
        future = pool.submit(function)

        def done(result):
            try:
                value = result.result()
                self.event.emit(kind, (True, value))
            except Exception as error:
                log.exception("Échec tâche %s", kind)
                self.event.emit(kind, (False, str(error)))

        future.add_done_callback(done)

    def load(self):
        if self.closing:
            return
        self._state(State.LOADING, "Préparation du modèle…")
        name = self.settings.model
        self._submit(
            self.engine_pool,
            "loaded",
            lambda: self.engine.load(name, lambda message: self.event.emit("progress", message)),
        )

    def toggle(self):
        if self.closing:
            return
        if self.state in (State.STARTING, State.RECORDING):
            self.recorder.stop()
            self._state(State.TRANSCRIBING, "Finalisation de l’audio…")
            self._sound(False)
        elif self.state in (State.IDLE, State.ERROR):
            if self.engine.model is None:
                self.load()
                return
            self.target = foreground()
            try:
                self.job, self.path = self.history.begin()
            except Exception:
                log.exception("Impossible de créer le journal audio")
                self._state(
                    State.ERROR, "Stockage indisponible. Vérifiez l’espace disque et les permissions."
                )
                self.notice.emit(self.message, True)
                return
            self.recorder = Recorder()
            self.cancelled = False
            recorder, path, job = self.recorder, self.path, self.job
            identity = self.settings.microphone
            self._state(State.STARTING, "Ouverture du microphone…")
            self._submit(
                self.io_pool,
                "captured",
                lambda: recorder.capture(
                    path,
                    identity,
                    lambda: self.event.emit("started", None),
                    lambda rate: self.history.update(job, sample_rate=rate),
                ),
            )

    def cancel(self):
        if self.state not in (State.STARTING, State.RECORDING):
            return
        self.cancelled = True
        self.recorder.stop()
        self._state(State.CANCELLING, "Annulation de la dictée…")

    def _sound(self, start: bool):
        if self.settings.sounds:
            self.io_pool.submit(winsound.Beep, 780 if start else 520, 65)

    def _transcribe(self, job: str, path: Path, rate: int):
        settings = replace(self.settings)
        self.transcription_started = time.monotonic()

        def work():
            text = self.engine.transcribe(path, rate, settings.language, settings.vocabulary)
            # Commit text before attempting any interaction with another application.
            self.history.update(
                job,
                text=text,
                status="saved" if text else "empty",
                detail="Texte enregistré." if text else "Aucune parole détectée.",
            )
            self.history.release_audio(job)
            return text

        self._state(State.TRANSCRIBING, "Transcription locale en cours…")
        self._submit(self.engine_pool, "transcribed", work)

    def recover(self, row: dict):
        if self.state not in (State.IDLE, State.ERROR) or self.engine.model is None:
            self.notice.emit("Attendez que le moteur soit prêt avant de récupérer l’audio.", True)
            return
        path = Path(row["audio"])
        if not path.is_file() or path.stat().st_size < 2:
            self.notice.emit(
                "Cet enregistrement ne contient plus d’audio. Vous pouvez supprimer cette entrée.", True
            )
            return
        self.job, self.path, self.target = row["id"], path, None
        self.history.update(self.job, duration=path.stat().st_size / (2 * row["sample_rate"]))
        self._transcribe(self.job, path, row["sample_rate"])

    @Slot(str, object)
    def _event(self, kind, result):
        try:
            self._handle_event(kind, result)
        except (OSError, sqlite3.Error):
            log.exception("Stockage indisponible pendant le traitement d’un résultat")
            self._state(State.ERROR, "Stockage indisponible. L’audio non traité reste dans le dossier local.")
            self.notice.emit(self.message, True)
            if self.closing:
                self._check_shutdown()

    def _handle_event(self, kind, result):
        if kind == "progress":
            if not self.closing:
                self._state(State.LOADING, result)
            return
        if kind == "started":
            self.record_started = time.monotonic()
            if self.state == State.STARTING:
                self._state(State.RECORDING, "Je vous écoute…")
                self._sound(True)
            return
        self.pending_tasks -= 1
        success, value = result
        if kind == "captured" and self.cancelled:
            # The microphone worker has closed its file before we remove it.
            self.history.delete(self.job)
            self.cancelled = False
            self.history_changed.emit()
            if self.closing:
                self._check_shutdown()
            else:
                self._state(State.IDLE, "Dictée annulée · audio supprimé.")
            return
        if self.closing:
            if kind == "captured" and success:
                duration, rate, warning = value
                self.history.update(
                    self.job,
                    duration=duration,
                    sample_rate=rate,
                    status="pending",
                    detail=warning or "Enregistrement interrompu à la fermeture. À récupérer.",
                )
            self._check_shutdown()
            return
        if not success:
            detail = {
                "loaded": "Impossible de préparer le modèle. Vérifiez la connexion pour le premier téléchargement, puis réessayez.",
                "captured": "Microphone indisponible. Vérifiez son branchement et l’autorisation Windows : Confidentialité > Microphone.",
                "transcribed": "La transcription a échoué. L’audio est conservé : utilisez Récupérer dans l’historique.",
                "inserted": "L’insertion a échoué. Le texte est conservé dans l’historique.",
            }[kind]
            if kind != "loaded" and self.job:
                self.history.update(self.job, status="error", detail=f"{detail} {value}")
                if kind == "captured" and (not self.path.exists() or self.path.stat().st_size == 0):
                    self.history.release_audio(self.job)
            self._state(State.ERROR, detail)
            self.notice.emit(f"{detail}\n\n{value}", True)
            self.history_changed.emit()
            return
        if kind == "loaded":
            self._state(State.IDLE, f"Prêt à dicter · {self.settings.model} · {value.upper()}")
            pending = self.history.recoverable()
            if pending:
                self.notice.emit(f"{len(pending)} enregistrement(s) à récupérer dans l’historique.", True)
            self.history_changed.emit()
        elif kind == "captured":
            duration, rate, warning = value
            self.history.update(self.job, duration=duration, sample_rate=rate, detail=warning)
            if warning:
                self.notice.emit(warning, True)
            if duration < 0.2:
                self.history.update(self.job, status="empty", detail="Enregistrement trop court.")
                self.history.release_audio(self.job)
                self._state(State.IDLE, "Enregistrement trop court · réessayez.")
                self.history_changed.emit()
            else:
                self._transcribe(self.job, self.path, rate)
        elif kind == "transcribed":
            self.transcription_seconds = time.monotonic() - self.transcription_started
            self.history_changed.emit()
            if not value:
                self._state(State.IDLE, "Aucune parole détectée.")
            elif self.target is None:
                self._state(State.IDLE, "Transcription récupérée dans l’historique.")
                self.notice.emit(self.message, False)
            else:
                target = self.target
                self._state(State.INSERTING, "Insertion du texte…")
                self._submit(self.io_pool, "inserted", lambda: insert_text(value, target))
        elif kind == "inserted":
            sent, detail = value
            self.history.update(self.job, status="sent" if sent else "saved", detail=detail)
            self.history_changed.emit()
            message = "Dictée terminée" if sent else "Texte conservé dans l’historique"
            self._state(State.IDLE, f"{message} · transcription en {self.transcription_seconds:.1f} s.")
            if not sent:
                self.notice.emit(detail, True)

    @property
    def busy(self):
        return self.state not in (State.IDLE, State.ERROR)

    def shutdown(self):
        self.closing = True
        if self.recorder:
            self.recorder.stop()
        self._state(State.CLOSING, "Fermeture · sauvegarde des tâches en cours…")
        self._check_shutdown()

    def _check_shutdown(self):
        # Wait for UI acknowledgement as well as worker completion before closing SQLite.
        if self.pending_tasks or self.closed:
            return
        self.closed = True
        self.engine_pool.shutdown(wait=False)
        self.io_pool.shutdown(wait=False)
        self.ready_to_quit.emit()
