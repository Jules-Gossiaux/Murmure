import threading

import pytest

import murmure.controller as module
from murmure.controller import Controller, State
from murmure.storage import History, Settings


class FakeRecorder:
    def __init__(self):
        self.stop_event = threading.Event()
        self.level = 0

    def stop(self):
        self.stop_event.set()

    def capture(self, path, identity, started, metadata):
        metadata(16000)
        path.write_bytes(b"\0" * 32000)
        started()
        assert self.stop_event.wait(3)
        return 1.0, 16000, ""


@pytest.fixture
def controller(tmp_path, monkeypatch, app):
    monkeypatch.setattr(module, "Recorder", FakeRecorder)
    monkeypatch.setattr(module, "foreground", lambda: object())
    history = History(tmp_path)
    controller = Controller(tmp_path, Settings(), history)
    controller.engine.model = object()
    controller.state = State.IDLE
    yield controller
    if controller.recorder:
        controller.recorder.stop()
    controller.engine_pool.shutdown(wait=True)
    controller.io_pool.shutdown(wait=True)
    app.processEvents()
    history.close()


def test_fast_double_toggle_and_commit_before_insertion(controller, monkeypatch, wait):
    monkeypatch.setattr(controller.engine, "transcribe", lambda *args: "Bonjour FSRS.")
    observed = []

    def insert(text, target):
        observed.append(controller.history.rows()[0]["text"])
        return True, "Envoyé"

    monkeypatch.setattr(module, "insert_text", insert)
    controller.toggle()
    controller.toggle()
    controller.toggle()  # Ignored while transcription is pending.
    wait(lambda: controller.state == State.IDLE)
    assert observed == ["Bonjour FSRS."]
    assert len(controller.history.rows()) == 1
    assert controller.history.rows()[0]["status"] == "sent"


def test_insertion_failure_keeps_text(controller, monkeypatch, wait):
    monkeypatch.setattr(controller.engine, "transcribe", lambda *args: "Toujours disponible")
    monkeypatch.setattr(module, "insert_text", lambda *args: (False, "Fenêtre fermée"))
    controller.toggle()
    controller.toggle()
    wait(lambda: controller.state == State.IDLE)
    assert controller.history.rows()[0]["text"] == "Toujours disponible"
    assert controller.history.rows()[0]["status"] == "saved"


def test_transcription_failure_keeps_audio_and_recovery(controller, monkeypatch, wait):
    def fail(*args):
        raise RuntimeError("engine error")

    monkeypatch.setattr(controller.engine, "transcribe", fail)
    controller.toggle()
    controller.toggle()
    wait(lambda: controller.state == State.ERROR)
    row = controller.history.recoverable()[0]
    assert controller.path.exists()
    monkeypatch.setattr(controller.engine, "transcribe", lambda *args: "Récupéré")
    controller.recover(row)
    wait(lambda: controller.state == State.IDLE)
    assert controller.history.rows()[0]["text"] == "Récupéré"
    assert not controller.path.exists()


def test_shutdown_waits_for_delivery_of_worker_result(controller, wait):
    closed = []
    controller.ready_to_quit.connect(lambda: closed.append(True))
    controller.toggle()
    controller.shutdown()
    assert not closed
    wait(lambda: bool(closed))
    assert closed == [True]
    assert controller.history.recoverable()[0]["duration"] == 1
    assert controller.path.exists()
    controller._check_shutdown()
    assert closed == [True]


def test_microphone_failure_is_recoverable_error(controller, monkeypatch, wait):
    def fail(*args):
        raise RuntimeError("No microphone")

    monkeypatch.setattr(FakeRecorder, "capture", fail)
    controller.toggle()
    wait(lambda: controller.state == State.ERROR)
    assert "Microphone" in controller.message
    assert controller.pending_tasks == 0


def test_empty_transcription_does_not_insert(controller, monkeypatch, wait):
    monkeypatch.setattr(controller.engine, "transcribe", lambda *args: "")
    monkeypatch.setattr(module, "insert_text", lambda *args: pytest.fail("Unexpected insertion"))
    controller.toggle()
    controller.toggle()
    wait(lambda: controller.state == State.IDLE)
    assert controller.history.rows()[0]["status"] == "empty"


def test_busy_hotkey_does_not_queue_new_recordings(controller):
    for state in (State.LOADING, State.TRANSCRIBING, State.INSERTING, State.CLOSING):
        controller.state = state
        controller.toggle()
        assert controller.history.rows() == []


def test_cancel_recording_deletes_audio_without_transcribing(controller, monkeypatch, wait):
    monkeypatch.setattr(
        controller.engine, "transcribe", lambda *args: pytest.fail("Cancelled audio transcribed")
    )
    controller.toggle()
    wait(lambda: controller.state == State.RECORDING)
    controller.cancel()
    controller.toggle()  # Must not start a second recording while the microphone is closing.
    wait(lambda: controller.state == State.IDLE)
    assert controller.history.rows() == []
    assert not controller.path.exists()


def test_cancel_while_microphone_is_opening(controller, monkeypatch, wait):
    monkeypatch.setattr(
        controller.engine, "transcribe", lambda *args: pytest.fail("Cancelled audio transcribed")
    )
    controller.toggle()
    controller.cancel()
    controller.shutdown()
    wait(lambda: controller.closed)
    assert controller.history.rows() == []
    assert not controller.path.exists()
