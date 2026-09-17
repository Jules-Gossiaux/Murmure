"""Small, typed Win32 boundary. No clipboard mutation during automatic insertion."""

from __future__ import annotations

import ctypes as ct
import os
import subprocess
import sys
import time
import winreg
from ctypes import wintypes as wt
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

user32 = ct.WinDLL("user32", use_last_error=True)
shell32 = ct.WinDLL("shell32", use_last_error=True)
shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wt.LPCWSTR]
shell32.SetCurrentProcessExplicitAppUserModelID.restype = ct.c_long
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ct.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.IsWindow.argtypes = [wt.HWND]
user32.RegisterHotKey.argtypes = [wt.HWND, ct.c_int, wt.UINT, wt.UINT]
user32.UnregisterHotKey.argtypes = [wt.HWND, ct.c_int]


class GUITHREADINFO(ct.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("flags", wt.DWORD),
        ("hwndActive", wt.HWND),
        ("hwndFocus", wt.HWND),
        ("hwndCapture", wt.HWND),
        ("hwndMenuOwner", wt.HWND),
        ("hwndMoveSize", wt.HWND),
        ("hwndCaret", wt.HWND),
        ("rcCaret", wt.RECT),
    ]


user32.GetGUIThreadInfo.argtypes = [wt.DWORD, ct.POINTER(GUITHREADINFO)]


def set_app_user_model_id(identifier: str = "JulesGossiaux.Murmure") -> None:
    """Give Python-launched windows the same taskbar identity as the packaged app."""
    result = shell32.SetCurrentProcessExplicitAppUserModelID(identifier)
    if result != 0:
        raise OSError(f"SetCurrentProcessExplicitAppUserModelID failed: HRESULT 0x{result & 0xFFFFFFFF:08x}")


@dataclass(frozen=True)
class Target:
    window: int
    focus: int
    process: int


def foreground() -> Target | None:
    window = user32.GetForegroundWindow()
    if not window:
        return None
    pid = wt.DWORD()
    thread = user32.GetWindowThreadProcessId(window, ct.byref(pid))
    info = GUITHREADINFO(cbSize=ct.sizeof(GUITHREADINFO))
    if not user32.GetGUIThreadInfo(thread, ct.byref(info)):
        return None
    return Target(int(window), int(info.hwndFocus or 0), pid.value)


class KEYBDINPUT(ct.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ct.c_size_t),
    ]


class MOUSEINPUT(ct.Structure):
    _fields_ = [
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ct.c_size_t),
    ]


class INPUTUNION(ct.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ct.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", wt.DWORD), ("data", INPUTUNION)]


user32.SendInput.argtypes = [wt.UINT, ct.POINTER(INPUT), ct.c_int]
user32.SendInput.restype = wt.UINT


def insert_text(text: str, target: Target | None) -> tuple[bool, str]:
    if not target or target.process == os.getpid():
        return False, "Aucun champ externe ciblé. Le texte est disponible dans l’historique."
    deadline = time.monotonic() + 2
    while any(user32.GetAsyncKeyState(key) & 0x8000 for key in (16, 17, 18, 91, 92)):
        if time.monotonic() > deadline:
            return (
                False,
                "Une touche de modification est restée enfoncée. Copiez le texte depuis l’historique.",
            )
        time.sleep(0.02)
    # SendInput cannot acknowledge consumption by the target application.
    # Recheck focus between batches; never reactivate a window behind the user's back.
    encoded = text.replace("\r\n", "\n").encode("utf-16-le")
    units = [int.from_bytes(encoded[i : i + 2], "little") for i in range(0, len(encoded), 2)]
    for start in range(0, len(units), 64):
        if foreground() != target or not user32.IsWindow(target.window):
            return False, "La fenêtre ou le champ actif a changé. Insertion interrompue ; texte conservé."
        events = []
        for unit in units[start : start + 64]:
            if unit == 10:
                events.extend(
                    [INPUT(type=1, ki=KEYBDINPUT(wVk=13)), INPUT(type=1, ki=KEYBDINPUT(wVk=13, dwFlags=2))]
                )
            else:
                events.extend(
                    [
                        INPUT(type=1, ki=KEYBDINPUT(wScan=unit, dwFlags=4)),
                        INPUT(type=1, ki=KEYBDINPUT(wScan=unit, dwFlags=6)),
                    ]
                )
        array = (INPUT * len(events))(*events)
        if user32.SendInput(len(array), array, ct.sizeof(INPUT)) != len(array):
            return (
                False,
                "Windows a bloqué l’insertion (application administrateur possible). Texte conservé.",
            )
        time.sleep(0.006)
    return True, "Texte envoyé à l’application."


class HotkeySignals(QObject):
    activated = Signal()
    cancelled = Signal()


class Hotkey(QAbstractNativeEventFilter):
    def __init__(self, window: int):
        super().__init__()
        self.window = window
        self.signals = HotkeySignals()
        self.identifier = 100
        self.current: tuple[int, int] | None = None
        self.suspended = False
        self.escape_registered = False

    def register(self, modifiers: int, key: int) -> None:
        if self.current == (modifiers, key) and not self.suspended:
            return
        new_id = 101 if self.identifier == 100 else 100
        if not user32.RegisterHotKey(self.window, new_id, modifiers | 0x4000, key):
            raise RuntimeError(
                "Ce raccourci est déjà utilisé ou réservé par Windows. Choisissez une autre combinaison."
            )
        if self.current and not self.suspended:
            user32.UnregisterHotKey(self.window, self.identifier)
        self.identifier, self.current = new_id, (modifiers, key)
        self.suspended = False

    def suspend(self):
        if self.current and not self.suspended:
            user32.UnregisterHotKey(self.window, self.identifier)
            self.suspended = True

    def resume(self):
        if self.suspended and self.current:
            self.register(*self.current)

    def set_escape(self, enabled: bool):
        if enabled == self.escape_registered:
            return
        if enabled:
            if not user32.RegisterHotKey(self.window, 102, 0x4000, 27):
                raise RuntimeError(
                    "Échap est occupé par une autre application. Utilisez le bouton Annuler dans Murmure."
                )
        else:
            user32.UnregisterHotKey(self.window, 102)
        self.escape_registered = enabled

    def nativeEventFilter(self, event_type, message):
        msg = wt.MSG.from_address(int(message))
        if msg.message == 0x0312 and msg.wParam == 102 and self.escape_registered:
            self.signals.cancelled.emit()
            return True, 0
        if msg.message == 0x0312 and msg.wParam == self.identifier and self.current and not self.suspended:
            self.signals.activated.emit()
            return True, 0
        return False, 0

    def close(self):
        self.set_escape(False)
        if self.current:
            user32.UnregisterHotKey(self.window, self.identifier)
            self.current = None
        self.suspended = False


def set_startup(enabled: bool) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        if enabled:
            if getattr(sys, "frozen", False):
                command = subprocess.list2cmdline([sys.executable, "--tray"])
            else:
                launcher = Path(__file__).resolve().parent.parent / "launch.py"
                pythonw = Path(sys.executable).with_name("pythonw.exe")
                command = subprocess.list2cmdline([str(pythonw), str(launcher), "--tray"])
            winreg.SetValueEx(key, "Murmure", 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, "Murmure")
            except FileNotFoundError:
                pass  # The requested registry state is already satisfied.
