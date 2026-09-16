"""Compare warmed models with synthetic French audio; never reads the user's history."""

import argparse
import gc
import json
import statistics
import subprocess
import time
import wave
from pathlib import Path

from murmure.engine import Engine
from murmure.storage import data_directory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["base", "small", "large-v3-turbo"])
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    root = Path("artifacts/model-benchmark")
    root.mkdir(parents=True, exist_ok=True)
    script = root / "synthesize.ps1"
    script.write_text(
        "Add-Type -AssemblyName System.Speech\n"
        "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$voice.SelectVoice('Microsoft Hortense Desktop')\n"
        "$voice.SetOutputToWaveFile((Join-Path $PSScriptRoot 'long-french.wav'))\n"
        "$voice.Speak('Ce matin, je prépare une nouvelle version de mon application. "
        "Il faut vérifier les raccourcis clavier, améliorer la lisibilité des paramètres et conserver les données sur cet ordinateur. "
        "Ensuite, je vais envoyer un message à mon collègue pour organiser notre réunion de demain matin. "
        "La dictée doit rester rapide, même lorsque la phrase contient plusieurs idées différentes.')\n"
        "$voice.Dispose()\n",
        encoding="utf-8-sig",
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-File", str(script)],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    clips = []
    for source in (Path("artifacts/integration/french-synthetic.wav"), root / "long-french.wav"):
        with wave.open(str(source)) as audio:
            rate = audio.getframerate()
            assert audio.getnchannels() == 1 and audio.getsampwidth() == 2
            raw = audio.readframes(audio.getnframes())
        path = root / f"{source.stem}.pcm"
        path.write_bytes(raw)
        clips.append((path, len(raw) / (2 * rate), rate))
    results = []
    for name in args.models:
        print(f"Preparing {name}", flush=True)
        engine = Engine(data_directory())
        engine.load(name, lambda message: print(message, flush=True))
        for path, duration, rate in clips:
            times = []
            for _ in range(args.repeats + 1):
                start = time.perf_counter()
                text = engine.transcribe(path, rate, "fr", "")
                times.append(time.perf_counter() - start)
            result = dict(
                model=name,
                device=engine.device,
                audio_seconds=duration,
                first_seconds=times[0],
                median_seconds=statistics.median(times[1:]),
                min_seconds=min(times[1:]),
                max_seconds=max(times[1:]),
                text=text,
            )
            results.append(result)
            print(json.dumps(result, ensure_ascii=True), flush=True)
            (root / "results.json").write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        del engine
        gc.collect()


if __name__ == "__main__":
    main()
