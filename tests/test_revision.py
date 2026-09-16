from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

import murmure.ui as ui_module
from murmure.controller import Controller, State
from murmure.shortcut import ShortcutEdit
from murmure.storage import History, Settings
from murmure.style import COLORS, apply_theme
from murmure.ui import MainWindow


class FakeHotkey:
    def __init__(self):
        self.current = (2, 32)
        self.suspended = False

    def register(self, mods, key):
        self.current = (mods, key)
        self.suspended = False

    def suspend(self):
        self.suspended = True

    def resume(self):
        self.suspended = False


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui_module, "microphones", lambda **kwargs: [])
    monkeypatch.setattr(ui_module, "set_startup", lambda enabled: None)
    history = History(tmp_path)
    controller = Controller(tmp_path, Settings(), history)
    controller.state = State.IDLE
    controller.engine.model = object()
    apply_theme(app, "light")
    window = MainWindow(controller, tmp_path)
    window.hotkey = FakeHotkey()
    window.show()
    app.processEvents()
    yield window
    window.flush_edits()
    window.allow_close = True
    window.close()
    controller.engine_pool.shutdown()
    controller.io_pool.shutdown()
    history.close()


def test_shortcut_capture_and_apply_immediately(window, app):
    window.navigate(3)
    window.key_edit.setFocus()
    app.processEvents()
    assert window.hotkey.suspended
    QTest.keyClick(
        window.key_edit, Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
    )
    assert window.key_edit.caption == "Ctrl+Alt+J"
    assert window.save_settings()
    assert window.hotkey.current == (3, 74)
    saved = Settings.load(window.directory)
    assert (saved.hotkey_mods, saved.hotkey_vk, saved.hotkey_label) == (3, 74, "Ctrl+Alt+J")


def test_native_azerty_key_preserves_windows_code(app):
    field = ShortcutEdit(2, 32, "Ctrl+Space")
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Ampersand, Qt.KeyboardModifier.ControlModifier, 0x02, 0x31, 0, "&"
    )
    field.keyPressEvent(event)
    assert field.virtual_key == 0x31  # Windows VK_1, not the Unicode value of '&'.
    assert field.modifiers == 2
    field.close()


def test_function_key_without_modifier(window):
    QTest.keyClick(window.key_edit, Qt.Key.Key_F9)
    assert window.save_settings()
    assert window.hotkey.current == (0, 120)
    assert Settings.load(window.directory).hotkey_mods == 0


def test_turbo_selection_updates_explanation_and_loads_model(window, monkeypatch):
    loaded = []
    monkeypatch.setattr(window.controller, "load", lambda: loaded.append(window.controller.settings.model))
    window.model.setCurrentIndex(window.model.findData("large-v3-turbo"))
    assert "Turbo" in window.model_description.text()
    assert window.save_settings()
    assert loaded == ["large-v3-turbo"]
    assert Settings.load(window.directory).model == "large-v3-turbo"


def click_dialog_button(caption):
    def click():
        from PySide6.QtWidgets import QApplication

        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                for button in widget.buttons():
                    if button.text() == caption:
                        button.click()
                        return
        raise AssertionError("Missing settings confirmation")

    QTimer.singleShot(30, click)


@pytest.mark.parametrize(
    "choice,leaves,saved",
    [("Annuler", False, False), ("Ne pas appliquer", True, False), ("Appliquer", True, True)],
)
def test_unsaved_settings_navigation(window, choice, leaves, saved):
    window.navigate(3)
    window.sounds.setChecked(True)
    click_dialog_button(choice)
    assert window.navigate(1) == leaves
    assert window.pages.currentIndex() == (1 if leaves else 3)
    assert window.controller.settings.sounds == saved
    if choice == "Ne pas appliquer":
        assert not window.sounds.isChecked()
    window.restore_settings_form()


def test_close_can_be_cancelled_without_losing_settings(window):
    window.navigate(3)
    window.sounds.setChecked(True)
    click_dialog_button("Annuler")
    window.close()
    assert window.isVisible()
    assert window.sounds.isChecked()
    window.restore_settings_form()


def test_edits_persist_and_keep_cursor(window, app, wait):
    identifier, _ = window.controller.history.begin()
    window.controller.history.update(identifier, text="Une dictée", audio="", status="saved")
    window.refresh_history()
    assert not window.latest_text.isReadOnly()
    window.latest_text.setFocus()
    window.latest_text.selectAll()
    QTest.keyClicks(window.latest_text, "Correction clavier")
    position = window.latest_text.textCursor().position()
    wait(lambda: not window.pending_edits)
    assert window.controller.history.rows()[0]["text"] == "Correction clavier"
    assert window.latest_text.textCursor().position() == position
    assert window.detail_text.toPlainText() == "Correction clavier"
    window.navigate(1)
    window.detail_text.selectAll()
    QTest.keyClicks(window.detail_text, "Depuis historique")
    window.navigate(0)  # Flush before the debounce timeout.
    assert window.latest_text.toPlainText() == "Depuis historique"
    assert window.controller.history.rows()[0]["text"] == "Depuis historique"


def test_edit_empty_transcription(window):
    identifier, _ = window.controller.history.begin()
    window.controller.history.update(identifier, audio="", status="empty")
    window.refresh_history()
    QTest.keyClicks(window.latest_text, "Texte ajoute")
    assert window.flush_edits()
    assert window.copy_latest.isEnabled()
    assert window.controller.history.rows()[0]["text"] == "Texte ajoute"


def test_theme_preview_discard_and_persistence(window, app):
    window.navigate(3)
    window.theme.setCurrentIndex(1)
    assert COLORS["dark"]["panel"] in app.styleSheet()
    click_dialog_button("Ne pas appliquer")
    window.navigate(0)
    assert COLORS["light"]["panel"] in app.styleSheet()
    window.navigate(3)
    window.theme.setCurrentIndex(1)
    assert window.save_settings()
    assert Settings.load(window.directory).theme == "dark"


def test_history_move_keeps_text_and_audio_and_survives_restart(tmp_path):
    root = tmp_path / "app"
    history = History(root)
    identifier, audio = history.begin()
    audio.write_bytes(b"audio")
    history.update(identifier, text="Dictée précieuse")
    destination = tmp_path / "mes textes"
    settings = Settings(history_folder=str(destination))
    history.relocate(destination, lambda: settings.save(root))
    assert history.directory == destination.resolve()
    assert not (root / "history.sqlite3").exists()
    assert audio.exists()
    history.close()
    saved = Settings.load(root)
    reopened = History(Path(saved.history_folder), audio_directory=root / "pending")
    assert reopened.rows()[0]["text"] == "Dictée précieuse"
    reopened.delete(identifier)
    assert not audio.exists()
    reopened.close()


def test_failed_settings_write_rolls_back_history_move(tmp_path):
    history = History(tmp_path / "old")
    identifier, _ = history.begin()
    history.update(identifier, text="Ne pas perdre")

    def fail():
        raise OSError("Disk full")

    with pytest.raises(OSError):
        history.relocate(tmp_path / "new", fail)
    assert not (tmp_path / "new" / "history.sqlite3").exists()
    assert history.rows()[0]["text"] == "Ne pas perdre"
    assert history.directory == (tmp_path / "old").resolve()
    history.close()


def test_move_never_overwrites_existing_history(tmp_path):
    history = History(tmp_path / "old")
    other = History(tmp_path / "other")
    identifier, _ = other.begin()
    other.update(identifier, text="Destination existante")
    with pytest.raises(FileExistsError):
        history.relocate(other.directory, lambda: None)
    assert other.rows()[0]["text"] == "Destination existante"
    history.close()
    other.close()


def test_history_folder_applied_through_settings(window):
    destination = window.directory / "archive"
    window.history_path.setText(str(destination))
    assert window.save_settings()
    assert window.controller.history.directory == destination.resolve()
    assert Settings.load(window.directory).history_folder == str(destination.resolve())


def test_theme_text_contrast():
    def luminance(color):
        channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    for theme in COLORS.values():
        for foreground, background in (
            ("text", "panel"),
            ("muted", "bg"),
            ("muted", "hero"),
            ("selected_text", "selected"),
            ("accent_text", "accent"),
            ("disabled_text", "disabled"),
        ):
            values = sorted([luminance(theme[foreground]), luminance(theme[background])])
            assert (values[1] + 0.05) / (values[0] + 0.05) >= 4.5, (foreground, background)
