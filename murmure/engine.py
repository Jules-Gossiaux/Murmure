from __future__ import annotations

import gc
import logging
import os
import tempfile
import wave
from pathlib import Path

from .storage import Settings

# Hugging Face is used only for model files, with telemetry disabled.
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

log = logging.getLogger(__name__)


class Engine:
    def __init__(self, directory: Path):
        self.default_cache = directory / "models"
        self.cache = Path(Settings.load(directory).models_folder or self.default_cache)
        self.model = None
        self.name = ""
        self.device = "cpu"
        self.model_path = ""

    def load(self, name: str, report) -> str:
        if self.name == name and self.model is not None:
            return self.device
        import ctranslate2
        from faster_whisper import WhisperModel
        from faster_whisper.utils import download_model

        report("Recherche du modèle local…")
        path = None
        for cache in dict.fromkeys((self.cache, self.default_cache)):
            try:
                candidate = download_model(name, cache_dir=str(cache), local_files_only=True)
                if all(
                    (Path(candidate) / file).is_file() and (Path(candidate) / file).stat().st_size
                    for file in ("model.bin", "config.json", "tokenizer.json")
                ):
                    path = candidate
                    break
            except Exception:
                log.debug("Modèle absent du cache %s", cache, exc_info=True)
        if path is None:
            report("Téléchargement du modèle… Vous pouvez continuer à utiliser l’interface.")
            path = download_model(name, cache_dir=str(self.cache))
        report("Chargement du moteur en mémoire…")
        device = "cpu"
        try:
            if ctranslate2.get_cuda_device_count() > 0:
                device = "cuda"
        except RuntimeError:
            log.info("Détection CUDA indisponible ; CPU utilisé", exc_info=True)
        self.model = None
        self.name = ""
        gc.collect()
        kwargs = dict(
            cpu_threads=max(1, min(8, (os.cpu_count() or 4) // 2)), num_workers=1, local_files_only=True
        )
        try:
            model = WhisperModel(
                path, device=device, compute_type="float16" if device == "cuda" else "int8", **kwargs
            )
        except Exception:
            if device != "cuda":
                raise
            log.warning("CUDA indisponible, repli CPU", exc_info=True)
            report("Accélération indisponible · chargement sur CPU…")
            device = "cpu"
            model = WhisperModel(path, device="cpu", compute_type="int8", **kwargs)
        self.model, self.name, self.device, self.model_path = model, name, device, path
        return device

    def transcribe(self, pcm: Path, rate: int, language: str, vocabulary: str) -> str:
        if self.model is None:
            raise RuntimeError("Le modèle n’est pas encore prêt.")
        # Bound memory for long dictations: decode and transcribe sequential 90-second chunks.
        # Chunks end near a quiet boundary when possible, keeping words together.
        import numpy as np
        from faster_whisper import WhisperModel
        from faster_whisper.audio import decode_audio

        texts = []
        with pcm.open("rb") as source:
            while raw := source.read(rate * 2 * 90):
                raw = raw[: len(raw) // 2 * 2]
                if not raw:
                    break
                if len(raw) == rate * 2 * 90:
                    samples = np.frombuffer(raw, dtype=np.int16)
                    tail = samples[-rate * 5 :].astype(np.float32)
                    window = max(1, rate // 10)
                    energy = np.mean(tail[: len(tail) // window * window].reshape(-1, window) ** 2, axis=1)
                    boundary = len(samples) - len(tail) + (int(np.argmin(energy)) + 1) * window
                    source.seek((boundary - len(samples)) * 2, 1)
                    raw = raw[: boundary * 2]
                with tempfile.SpooledTemporaryFile(max_size=12_000_000) as wav_file:
                    with wave.open(wav_file, "wb") as wav:
                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(rate)
                        wav.writeframes(raw)
                    wav_file.seek(0)
                    audio = decode_audio(wav_file)
                kwargs = dict(
                    language=None if language == "auto" else language,
                    beam_size=1,
                    best_of=1,
                    temperature=0.0,
                    vad_filter=True,
                    condition_on_previous_text=False,
                    vad_parameters={"min_silence_duration_ms": 350, "speech_pad_ms": 180},
                    hotwords=vocabulary.strip() or None,
                )
                try:
                    segments, _ = self.model.transcribe(audio, **kwargs)
                    chunk = " ".join(s.text.strip() for s in segments).strip()
                except Exception:
                    if self.device != "cuda":
                        raise
                    log.warning("Échec CUDA pendant l’inférence ; reprise CPU", exc_info=True)
                    self.model = None
                    gc.collect()
                    self.model = WhisperModel(
                        self.model_path,
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=max(1, min(8, (os.cpu_count() or 4) // 2)),
                        local_files_only=True,
                    )
                    self.device = "cpu"
                    segments, _ = self.model.transcribe(audio, **kwargs)
                    chunk = " ".join(s.text.strip() for s in segments).strip()
                if chunk:
                    texts.append(chunk)
        return " ".join(texts)
