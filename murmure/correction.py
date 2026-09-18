"""Small, local text correction model loaded only when the feature is enabled."""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

REPOSITORY = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
FILENAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"


class CorrectionEngine:
    def __init__(self, directory: Path):
        self.default_cache = directory / "models"
        self.cache = self.default_cache
        self.model = None
        self.model_path: Path | None = None

    @property
    def downloaded(self) -> bool:
        path = self.cache / "correction" / FILENAME
        return path.is_file() and path.stat().st_size >= 100_000_000

    def load(self, report) -> None:
        if self.model is not None:
            return
        path = self.cache / "correction" / FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.stat().st_size < 100_000_000:
            report("Téléchargement du correcteur local (environ 491 Mo)…")
            from huggingface_hub import hf_hub_download

            path = Path(
                hf_hub_download(
                    repo_id=REPOSITORY,
                    filename=FILENAME,
                    local_dir=str(path.parent),
                )
            )
        report("Chargement du correcteur local…")
        from llama_cpp import Llama

        self.model = Llama(
            model_path=str(path),
            n_ctx=2048,
            n_threads=max(1, min(8, (os.cpu_count() or 4) // 2)),
            n_batch=256,
            n_gpu_layers=0,
            verbose=False,
        )
        self.model_path = path

    def correct(self, text: str, language: str, report=lambda _message: None) -> str:
        if not text.strip():
            return text
        self.load(report)
        language_name = "français" if language in {"fr", "auto"} else language
        response = self.model.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es un correcteur discret. Corrige uniquement l’orthographe, la grammaire, "
                        "la conjugaison, la ponctuation et les mots manifestement mal transcrits. "
                        "Conserve le sens, le ton, les noms propres et la mise en forme. "
                        "Ne donne aucune explication et ne mets pas de guillemets."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Corrige ce texte en {language_name}, puis renvoie uniquement la version corrigée :\n{text}",
                },
            ],
            temperature=0.05,
            top_p=0.9,
            max_tokens=min(1024, max(128, len(text) * 3)),
        )
        corrected = response["choices"][0]["message"]["content"].strip()
        return corrected or text
