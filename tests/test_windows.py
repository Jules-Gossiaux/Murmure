import ctypes as ct
import os

import pytest
from PySide6.QtWidgets import QWidget

import murmure.windows as module
from murmure.windows import INPUT, Hotkey, Target, insert_text, user32


def test_input_layout_matches_windows_64bit():
    assert ct.sizeof(INPUT) == (40 if ct.sizeof(ct.c_void_p) == 8 else 28)


def test_no_target_and_own_window_never_insert():
    assert not insert_text("Bonjour", None)[0]
    assert not insert_text("Bonjour", Target(1, 1, os.getpid()))[0]


def test_changed_focus_blocks_insertion(monkeypatch):
    monkeypatch.setattr(module, "foreground", lambda: Target(3, 4, 9000))
    assert not insert_text("Bonjour", Target(1, 2, 9000))[0]


def test_register_conflict_keeps_previous_hotkey(app):
    widget = QWidget()
    hotkey = Hotkey(int(widget.winId()))
    try:
        hotkey.register(3, 0x87)  # Ctrl+Alt+F24
        assert user32.RegisterHotKey(int(widget.winId()), 222, 3 | 0x4000, 0x86)
        with pytest.raises(RuntimeError):
            hotkey.register(3, 0x86)
        assert hotkey.current == (3, 0x87)
        hotkey.register(3, 0x85)
        assert hotkey.current == (3, 0x85)
    finally:
        hotkey.close()
        user32.UnregisterHotKey(int(widget.winId()), 222)
        widget.close()
