import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from murmure.storage import History, Settings


def test_settings_roundtrip(tmp_path):
    settings = Settings(vocabulary="FSRS\nÉléonore", hotkey_mods=3, hotkey_vk=68, hotkey_label="Ctrl+Alt+D")
    settings.save(tmp_path)
    assert Settings.load(tmp_path) == settings
    assert not list(tmp_path.glob("*.tmp"))


def test_broken_settings_backed_up(tmp_path):
    (tmp_path / "settings.json").write_text("{broken", encoding="utf-8")
    assert Settings.load(tmp_path) == Settings()
    assert len(list(tmp_path.glob("settings.invalid-*.json"))) == 1


def test_settings_validation(tmp_path):
    (tmp_path / "settings.json").write_text(
        json.dumps({"model": "nonsense", "sounds": "false", "hotkey_vk": -1})
    )
    assert Settings.load(tmp_path) == Settings()


def test_history_reopen_unicode_search_and_delete(tmp_path):
    history = History(tmp_path)
    identifier, audio = history.begin()
    audio.write_bytes(b"audio")
    history.update(identifier, text="ÉTÉ FSRS 100% _", duration=3.4, status="saved")
    history.close()
    history = History(tmp_path)
    assert history.rows("été")[0]["id"] == identifier
    assert history.rows("100%")[0]["duration"] == 3.4
    assert history.rows("_'") == []
    history.delete(identifier)
    assert not audio.exists()
    assert history.rows() == []
    history.close()


def test_interrupted_recording_remains_recoverable(tmp_path):
    history = History(tmp_path)
    identifier, audio = history.begin()
    audio.write_bytes(b"\0" * 64000)
    history.update(identifier, sample_rate=32000)
    history.close()
    history = History(tmp_path)
    assert history.recoverable()[0]["sample_rate"] == 32000
    assert history.recoverable()[0]["id"] == identifier
    assert audio.stat().st_size == 64000
    history.clear()
    assert not audio.exists()
    history.close()


def test_commit_text_before_removing_audio(tmp_path):
    history = History(tmp_path)
    identifier, audio = history.begin()
    audio.write_bytes(b"\0\0")
    history.update(identifier, text="Conservé", status="saved")
    history.release_audio(identifier)
    assert history.rows()[0]["text"] == "Conservé"
    assert history.rows()[0]["audio"] == ""
    history.close()


def test_history_concurrent_reads_and_writes(tmp_path):
    history = History(tmp_path)

    def write(index):
        identifier, _ = history.begin()
        history.update(identifier, text=f"dictée {index}")
        history.rows()

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(write, range(40)))
    assert len(history.rows()) == 40
    assert history.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with pytest.raises(ValueError):
        history.update("irrelevant", **{"text = ''; DROP TABLE entries; --": "bad"})
    history.close()
