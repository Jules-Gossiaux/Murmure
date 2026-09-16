from types import SimpleNamespace

import numpy as np

from murmure.engine import Engine


def test_cached_model_is_reused_without_network(tmp_path, monkeypatch):
    import ctranslate2
    import faster_whisper
    import faster_whisper.utils

    calls = []
    for name in ("model.bin", "config.json", "tokenizer.json"):
        (tmp_path / name).write_bytes(b"test")

    def download(name, **kwargs):
        assert kwargs["local_files_only"] is True
        return str(tmp_path)

    monkeypatch.setattr(faster_whisper.utils, "download_model", download)
    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: 0)

    def model(*args, **kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(faster_whisper, "WhisperModel", model)
    engine = Engine(tmp_path)
    assert engine.load("base", lambda message: None) == "cpu"
    first = engine.model
    engine.load("base", lambda message: None)
    assert engine.model is first
    assert len(calls) == 1
    assert calls[0]["compute_type"] == "int8"


def test_cuda_loading_falls_back_to_cpu(tmp_path, monkeypatch):
    import ctranslate2
    import faster_whisper
    import faster_whisper.utils

    for name in ("model.bin", "config.json", "tokenizer.json"):
        (tmp_path / name).write_bytes(b"test")

    monkeypatch.setattr(faster_whisper.utils, "download_model", lambda *args, **kwargs: str(tmp_path))
    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: 1)

    def model(*args, **kwargs):
        if kwargs["device"] == "cuda":
            raise RuntimeError("missing cudnn DLL")
        return object()

    monkeypatch.setattr(faster_whisper, "WhisperModel", model)
    engine = Engine(tmp_path)
    assert engine.load("base", lambda message: None) == "cpu"
    assert engine.model is not None


def test_generator_cuda_error_retries_on_cpu(tmp_path, monkeypatch):
    import faster_whisper

    class GPU:
        def transcribe(self, audio, **kwargs):
            def segments():
                yield SimpleNamespace(text="Partial must not duplicate")
                raise RuntimeError("CUDA failed during iteration")

            return segments(), None

    class CPU:
        def transcribe(self, audio, **kwargs):
            assert kwargs["hotwords"] == "FSRS"
            assert kwargs["language"] == "fr"
            return iter([SimpleNamespace(text="Reprise complète")]), None

    monkeypatch.setattr(faster_whisper, "WhisperModel", lambda *args, **kwargs: CPU())
    engine = Engine(tmp_path)
    engine.model, engine.device = GPU(), "cuda"
    pcm = tmp_path / "audio.pcm"
    pcm.write_bytes(b"\0" * 32000)
    assert engine.transcribe(pcm, 16000, "fr", "FSRS") == "Reprise complète"
    assert engine.device == "cpu"


def test_long_recording_chunking_does_not_drop_samples(tmp_path):
    lengths = []

    class Model:
        def transcribe(self, audio, **kwargs):
            lengths.append(len(audio))
            return iter([SimpleNamespace(text="Phrase")]), None

    engine = Engine(tmp_path)
    engine.model = Model()
    pcm = tmp_path / "long.pcm"
    audio = np.ones(16000 * 184, dtype=np.int16)
    pcm.write_bytes(audio.tobytes())
    assert engine.transcribe(pcm, 16000, "auto", "") == "Phrase Phrase Phrase"
    assert sum(lengths) == len(audio)
    assert max(lengths) <= 16000 * 90
