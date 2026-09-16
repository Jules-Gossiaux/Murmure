"""Opt-in Windows checks: creates its own edit window, briefly opens the microphone.

Run from the project root after preparing the base model. No network transcription.
"""

from __future__ import annotations

import ctypes as ct
import json
import os
import subprocess
import sys
import threading
import time
import wave
from ctypes import wintypes as wt
from pathlib import Path


def target_window():
    user = ct.WinDLL("user32", use_last_error=True)
    user.CreateWindowExW.argtypes = [
        wt.DWORD,
        wt.LPCWSTR,
        wt.LPCWSTR,
        wt.DWORD,
        ct.c_int,
        ct.c_int,
        ct.c_int,
        ct.c_int,
        wt.HWND,
        wt.HMENU,
        wt.HINSTANCE,
        wt.LPVOID,
    ]
    user.CreateWindowExW.restype = wt.HWND
    user.ShowWindow.argtypes = [wt.HWND, ct.c_int]
    user.SetFocus.argtypes = [wt.HWND]
    user.SetForegroundWindow.argtypes = [wt.HWND]
    parent = user.CreateWindowExW(
        0, "STATIC", "Murmure · fenêtre de validation", 0x10CF0000, 80, 80, 620, 240, None, None, None, None
    )
    edit = user.CreateWindowExW(0, "EDIT", "", 0x50001044, 10, 10, 580, 160, parent, None, None, None)
    user.ShowWindow(parent, 5)
    user.SetForegroundWindow(parent)
    user.SetFocus(edit)
    print(json.dumps({"window": int(parent), "edit": int(edit), "pid": os.getpid()}), flush=True)
    msg = wt.MSG()
    user.IsWindow.argtypes = [wt.HWND]
    while user.IsWindow(parent):
        while user.PeekMessageW(ct.byref(msg), None, 0, 0, 1):
            user.TranslateMessage(ct.byref(msg))
            user.DispatchMessageW(ct.byref(msg))
        time.sleep(0.005)


def main():
    from PySide6.QtWidgets import QApplication, QWidget

    from murmure.audio import Recorder
    from murmure.controller import Controller
    from murmure.engine import Engine
    from murmure.storage import History, Settings, data_directory
    from murmure.widgets import Overlay
    from murmure.windows import INPUT, KEYBDINPUT, Hotkey, foreground, insert_text, user32

    artifacts = Path("artifacts/integration").resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    results = {}
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    def pump(duration=0.1):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.005)

    helper = subprocess.Popen(
        [sys.executable, __file__, "--target"],
        stdout=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    window = QWidget()
    hotkey = Hotkey(int(window.winId()))
    history = History(artifacts)
    controller = Controller(artifacts, Settings(), history)
    overlay = Overlay(controller)
    try:
        handles = json.loads(helper.stdout.readline())
        user32.SetForegroundWindow.argtypes = [wt.HWND]
        user32.SetFocus.argtypes = [wt.HWND]
        thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        own_thread = ct.windll.kernel32.GetCurrentThreadId()
        helper_thread = user32.GetWindowThreadProcessId(handles["window"], None)
        user32.AttachThreadInput(own_thread, thread, True)
        user32.AttachThreadInput(own_thread, helper_thread, True)
        user32.SetForegroundWindow(handles["window"])
        user32.SetFocus(handles["edit"])
        user32.AttachThreadInput(own_thread, helper_thread, False)
        user32.AttachThreadInput(own_thread, thread, False)
        pump()
        target = foreground()
        assert target and target.process == handles["pid"] and target.focus == handles["edit"], (
            target,
            handles,
        )
        clipboard_before = app.clipboard().text()
        overlay.show_state("recording", "Test")
        pump()
        assert foreground() == target, "Overlay stole focus"
        overlay.hide()
        results["overlay_preserves_focus"] = True

        text = "Bonjour, été, cœur, FSRS ! 日本語 🙂"
        assert insert_text(text, target)[0]
        pump()
        user32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        user32.SendMessageW.restype = wt.LPARAM
        buffer = ct.create_unicode_buffer(512)
        user32.SendMessageW(handles["edit"], 0xD, len(buffer), ct.addressof(buffer))
        assert buffer.value == text, repr(buffer.value)
        assert app.clipboard().text() == clipboard_before
        results["unicode_insertion_and_clipboard"] = True

        app.installNativeEventFilter(hotkey)
        hotkey.register(3, 0x87)
        activations = []
        hotkey.signals.activated.connect(lambda: activations.append(True))
        events = [
            INPUT(type=1, ki=KEYBDINPUT(wVk=key, dwFlags=flags))
            for key, flags in ((17, 0), (18, 0), (0x87, 0), (0x87, 0), (0x87, 2), (18, 2), (17, 2))
        ]
        array = (INPUT * len(events))(*events)
        assert user32.SendInput(len(array), array, ct.sizeof(INPUT)) == len(array)
        pump(0.3)
        assert activations == [True], activations
        results["global_hotkey_and_no_repeat"] = True
        hotkey.register(3, 0x86)
        assert user32.SendInput(len(array), array, ct.sizeof(INPUT)) == len(array)
        pump()
        assert len(activations) == 1, "Old shortcut is still active"
        for event in array:
            if event.ki.wVk == 0x87:
                event.ki.wVk = 0x86
        assert user32.SendInput(len(array), array, ct.sizeof(INPUT)) == len(array)
        pump()
        assert len(activations) == 2, "New shortcut was not activated"
        results["hotkey_replacement"] = True
        cancellations = []
        hotkey.signals.cancelled.connect(lambda: cancellations.append(True))
        hotkey.set_escape(True)
        escape = (INPUT * 2)(
            INPUT(type=1, ki=KEYBDINPUT(wVk=27)), INPUT(type=1, ki=KEYBDINPUT(wVk=27, dwFlags=2))
        )
        assert user32.SendInput(2, escape, ct.sizeof(INPUT)) == 2
        pump()
        assert cancellations == [True]
        hotkey.set_escape(False)
        assert user32.RegisterHotKey(int(window.winId()), 333, 0x4000, 27)
        user32.UnregisterHotKey(int(window.winId()), 333)
        results["global_escape_and_release"] = True
        hotkey.close()
    finally:
        hotkey.close()
        overlay.hide()
        user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        user32.PostMessageW(handles["window"], 0x10, 0, 0)
        helper.wait(timeout=5)
        window.close()
        controller.engine_pool.shutdown()
        controller.io_pool.shutdown()
        history.close()

    if "--windows-only" in sys.argv:
        (artifacts / "windows-revision.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps(results, indent=2))
        return

    # Open the actual default microphone once, without retaining or transcribing this capture.
    recorder = Recorder()
    timer = threading.Timer(1.0, recorder.stop)
    capture = artifacts / "microphone-check.pcm"
    try:
        started = time.monotonic()
        duration, rate, warning = recorder.capture(capture, "", timer.start, lambda rate: None)
        assert duration > 0.3, duration
        assert not warning, warning
        results["microphone"] = {
            "duration": duration,
            "rate": rate,
            "wall_seconds": time.monotonic() - started,
        }
    finally:
        timer.cancel()
        capture.unlink(missing_ok=True)

    wav_path = artifacts / "french-synthetic.wav"
    ps_script = artifacts / "synthesize.ps1"
    ps_script.write_text(
        "Add-Type -AssemblyName System.Speech\n"
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$synth.SelectVoice('Microsoft Hortense Desktop')\n"
        "$synth.SetOutputToWaveFile((Join-Path $PSScriptRoot 'french-synthetic.wav'))\n"
        "$synth.Speak('Bonjour, ceci est un test de dictée vocale. Le texte reste sur cet ordinateur.')\n"
        "$synth.Dispose()\n",
        encoding="utf-8-sig",
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-File", str(ps_script)],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    with wave.open(str(wav_path)) as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        rate = wav.getframerate()
        pcm = artifacts / "french-synthetic.pcm"
        pcm.write_bytes(wav.readframes(wav.getnframes()))
        duration = wav.getnframes() / rate
    os.environ["HF_HUB_OFFLINE"] = "1"
    engine = Engine(data_directory())
    begin = time.monotonic()
    engine.load("base", lambda message: print(message, flush=True))
    load_seconds = time.monotonic() - begin
    begin = time.monotonic()
    transcript = engine.transcribe(pcm, rate, "fr", "")
    transcription_seconds = time.monotonic() - begin
    assert "bonjour" in transcript.lower(), transcript
    assert "ordinateur" in transcript.lower(), transcript
    model_identity = id(engine.model)
    engine.load("base", lambda message: None)
    assert id(engine.model) == model_identity
    silence = artifacts / "silence.pcm"
    silence.write_bytes(b"\0" * 32000)
    assert engine.transcribe(silence, 16000, "fr", "FSRS") == ""
    results["offline_transcription"] = {
        "text": transcript,
        "audio_seconds": duration,
        "load_seconds": load_seconds,
        "transcription_seconds": transcription_seconds,
        "device": engine.device,
        "model_reused": True,
        "silence_filtered": True,
    }
    (artifacts / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    if "--target" in sys.argv:
        target_window()
    else:
        main()
