"""Capture one Windows shortcut immediately, including non-US keyboard layouts."""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QLineEdit


class ShortcutEdit(QLineEdit):
    capture_started = Signal()
    capture_finished = Signal()
    shortcut_changed = Signal()

    def __init__(self, modifiers: int, key: int, caption: str):
        super().__init__()
        self.setReadOnly(True)
        self.setObjectName("shortcut")
        self.setPlaceholderText("Appuyez sur une combinaison…")
        self.set_shortcut(modifiers, key, caption)

    def set_shortcut(self, modifiers: int, key: int, caption: str):
        self.modifiers, self.virtual_key, self.caption = modifiers, key, caption
        self.setText(caption)

    def focusInEvent(self, event):
        self.capture_started.emit()
        super().focusInEvent(event)
        self.selectAll()

    def focusOutEvent(self, event):
        self.setText(self.caption)
        super().focusOutEvent(event)
        self.capture_finished.emit()

    def event(self, event):
        if event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
                self.keyPressEvent(event)
                return True
        return super().event(event)

    def keyPressEvent(self, event):
        event.accept()
        if event.isAutoRepeat():
            return
        key, modifiers = event.key(), event.modifiers()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr):
            return
        if key == Qt.Key.Key_Escape:
            self.setText(self.caption)
            self.clearFocus()
            return
        mods = (
            (2 if modifiers & Qt.KeyboardModifier.ControlModifier else 0)
            | (1 if modifiers & Qt.KeyboardModifier.AltModifier else 0)
            | (4 if modifiers & Qt.KeyboardModifier.ShiftModifier else 0)
            | (8 if modifiers & Qt.KeyboardModifier.MetaModifier else 0)
        )
        function_key = Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24
        if not mods & (1 | 2 | 8) and not function_key:
            self.setText("Ajoutez Ctrl, Alt ou Windows à cette touche")
            return
        # Native virtual keys retain the actual Windows mapping (AZERTY punctuation/digits included).
        vk = event.nativeVirtualKey()
        if not vk:
            special = {
                Qt.Key.Key_Space: 32,
                Qt.Key.Key_Return: 13,
                Qt.Key.Key_Tab: 9,
                Qt.Key.Key_Backspace: 8,
                Qt.Key.Key_Delete: 46,
                Qt.Key.Key_Insert: 45,
                Qt.Key.Key_Home: 36,
                Qt.Key.Key_End: 35,
                Qt.Key.Key_PageUp: 33,
                Qt.Key.Key_PageDown: 34,
                Qt.Key.Key_Left: 37,
                Qt.Key.Key_Up: 38,
                Qt.Key.Key_Right: 39,
                Qt.Key.Key_Down: 40,
            }
            vk = 112 + int(key) - int(Qt.Key.Key_F1) if function_key else special.get(key, int(key))
        if not 1 <= vk <= 254:
            self.setText("Cette touche n’est pas prise en charge")
            return
        caption = QKeySequence(event.keyCombination()).toString(QKeySequence.SequenceFormat.PortableText)
        self.set_shortcut(mods, vk, caption)
        self.shortcut_changed.emit()
