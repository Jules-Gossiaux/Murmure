from __future__ import annotations

import logging
import os
import queue
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)


def microphones(refresh: bool = False) -> list[tuple[str, str]]:
    if refresh:
        # PortAudio snapshots devices at initialization. Only call when capture is idle.
        # These sounddevice entry points are pinned and covered by the installed-version checks.
        sd._terminate()
        sd._initialize()
    devices = sd.query_devices()
    hosts = sd.query_hostapis()
    return [
        (f"{hosts[d['hostapi']]['name']}|{d['name']}", f"{d['name']} · {hosts[d['hostapi']]['name']}")
        for d in devices
        if d["max_input_channels"] > 0
    ]


def resolve_device(identity: str) -> int | None:
    if not identity:
        return None
    hosts = sd.query_hostapis()
    for index, device in enumerate(sd.query_devices()):
        if (
            device["max_input_channels"]
            and f"{hosts[device['hostapi']]['name']}|{device['name']}" == identity
        ):
            return index
    raise RuntimeError(
        "Le microphone sélectionné est débranché. Choisissez un autre microphone dans les paramètres."
    )


class Recorder:
    def __init__(self):
        self.stop_event = threading.Event()
        self.level = 0.0

    def stop(self):
        self.stop_event.set()

    def capture(self, path: Path, identity: str, started, metadata) -> tuple[float, int, str]:
        device = resolve_device(identity)
        info = sd.query_devices(device, "input")
        rate = int(info["default_samplerate"])
        metadata(rate)
        frames = 0
        errors: list[str] = []
        chunks: queue.Queue[bytes] = queue.Queue(maxsize=250)
        last_frame = time.monotonic()
        # Unbuffered PCM remains readable after interruption; no WAV header to repair.
        with path.open("wb", buffering=0) as output:

            def callback(indata, count, timing, status):
                nonlocal last_frame
                if self.stop_event.is_set():
                    raise sd.CallbackStop
                try:
                    chunks.put_nowait(bytes(indata))
                    last_frame = time.monotonic()
                    if status.input_overflow:
                        errors.append("Des échantillons audio ont été perdus (microphone surchargé).")
                        self.stop_event.set()
                except queue.Full:
                    errors.append("Le disque ne suit pas l’enregistrement. Audio partiel conservé.")
                    self.stop_event.set()
                    raise sd.CallbackAbort

            def write_chunk(chunk):
                nonlocal frames
                if output.write(chunk) != len(chunk):
                    raise OSError("Écriture audio incomplète. Vérifiez l’espace disque.")
                frames += len(chunk) // 2
                samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                self.level = float(np.sqrt(np.mean(samples * samples)) / 32768)

            with sd.RawInputStream(
                samplerate=rate,
                device=device,
                channels=1,
                dtype="int16",
                blocksize=max(256, rate // 50),
                callback=callback,
            ) as stream:
                started()
                while not self.stop_event.is_set():
                    try:
                        write_chunk(chunks.get(timeout=0.025))
                    except queue.Empty:
                        pass  # A short wait permits device-disconnection detection.
                    if not stream.active or time.monotonic() - last_frame > 3:
                        errors.append(
                            "Le microphone s’est arrêté ou a été déconnecté. Audio partiel conservé."
                        )
                        break
                stream.abort()
                while not chunks.empty():
                    write_chunk(chunks.get_nowait())
            os.fsync(output.fileno())
        self.level = 0
        return frames / rate, rate, " ".join(dict.fromkeys(errors))
