from __future__ import annotations

import argparse
import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLockFile, QTimer, QTranslator
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .controller import Controller, State
from .storage import History, Settings, data_directory
from .style import apply_theme
from .ui import MainWindow
from .widgets import Overlay, app_icon
from .windows import Hotkey, set_app_user_model_id


def configure_logging(directory: Path):
    handler = RotatingFileHandler(
        directory / "murmure.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tray", action="store_true")
    parser.add_argument("--load-model", action="store_true", help="Also load the engine during a smoke test")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Open UI, capture screenshots, exit without loading model"
    )
    args = parser.parse_args()
    # Must happen before QApplication creates the first native window. This prevents
    # a Python-launched development build from being grouped under the Python icon.
    try:
        set_app_user_model_id()
    except OSError:
        logging.getLogger(__name__).warning("Windows taskbar identity unavailable", exc_info=True)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Murmure")
    app.setOrganizationName("Murmure")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    translator = QTranslator(app)
    if translator.load("qtbase_fr", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    directory = data_directory()
    lock = QLockFile(str(directory / "instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(
            None,
            "Murmure est déjà ouvert",
            "Retrouvez Murmure dans la zone de notification Windows (icônes masquées près de l’horloge).",
        )
        return 0
    configure_logging(directory)

    def exception_hook(kind, value, traceback):
        logging.getLogger(__name__).critical("Erreur non gérée", exc_info=(kind, value, traceback))
        QMessageBox.critical(
            None, "Murmure · erreur", f"Une erreur est survenue : {value}\n\nLe journal est dans {directory}."
        )

    sys.excepthook = exception_hook
    settings = Settings.load(directory)
    apply_theme(app, settings.theme)
    history_directory = Path(settings.history_folder) if settings.history_folder else directory
    if settings.history_folder and not (history_directory / "history.sqlite3").is_file():
        QMessageBox.critical(
            None,
            "Historique introuvable",
            f"Le dossier d’historique configuré est indisponible :\n{history_directory}\n\nReconnectez ce dossier ou corrigez history_folder dans {directory / 'settings.json'}. Aucun historique vide n’a été créé.",
        )
        lock.unlock()
        return 1
    history = History(history_directory, audio_directory=directory / "pending")
    controller = Controller(directory, settings, history)
    window = MainWindow(controller, directory)
    icon = app_icon()
    window.setWindowIcon(icon)
    app.setWindowIcon(icon)
    overlay = Overlay(controller)
    controller.changed.connect(overlay.show_state)
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("Murmure · Dictée locale")
    menu = QMenu()
    for title, index in (("Ouvrir Murmure", 0), ("Historique", 1), ("Vocabulaire", 2), ("Paramètres", 3)):
        action = QAction(title, menu)
        action.triggered.connect(lambda checked=False, i=index: window.show_page(i))
        menu.addAction(action)
    menu.addSeparator()
    toggle_action = menu.addAction("Commencer une dictée")

    def tray_toggle():
        if controller.state in (State.RECORDING, State.STARTING):
            controller.toggle()
        else:
            window.start_from_ui()

    toggle_action.triggered.connect(tray_toggle)
    menu.addSeparator()
    quit_action = menu.addAction("Quitter Murmure")
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: window.show_page(0) if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
    )
    tray.messageClicked.connect(lambda: window.show_page(1))

    def notice(text, error):
        window.show_notice(text, error)
        if not window.isVisible() and tray.isVisible():
            tray.showMessage(
                "Murmure",
                text,
                QSystemTrayIcon.MessageIcon.Warning if error else QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    controller.notice.connect(notice)

    def state_changed(state, message):
        try:
            hotkey.set_escape(state in ("starting", "recording"))
        except RuntimeError as error:
            notice(str(error), True)
        toggle_action.setEnabled(state in ("idle", "error", "recording", "starting"))
        toggle_action.setText(
            "Terminer la dictée" if state in ("recording", "starting") else "Commencer une dictée"
        )
        tray.setToolTip("Murmure · " + message)

    controller.changed.connect(state_changed)
    hotkey = Hotkey(int(window.winId()))
    window.hotkey = hotkey
    app.installNativeEventFilter(hotkey)
    hotkey.signals.activated.connect(controller.toggle)
    hotkey.signals.cancelled.connect(controller.cancel)
    try:
        hotkey.register(settings.hotkey_mods, settings.hotkey_vk)
    except RuntimeError as error:
        logging.getLogger(__name__).warning("Raccourci indisponible: %s", error)
        QTimer.singleShot(300, lambda message=str(error): notice(message, True))
        args.tray = False
    tray.show()
    if not QSystemTrayIcon.isSystemTrayAvailable():
        controller.settings.close_to_tray = False
        args.tray = False

    def quit_app():
        if controller.closing:
            return
        if not window.prepare_to_leave():
            return
        if controller.busy:
            text = (
                "La tâche est en cours. L’enregistrement sera conservé pour récupération. "
                "Une transcription ou un téléchargement en cours sera terminé avant la fermeture."
            )
            if (
                QMessageBox.question(
                    window,
                    "Quitter Murmure ?",
                    text,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        hotkey.close()
        overlay.hide()
        quit_action.setEnabled(False)
        controller.shutdown()

    def finish():
        hotkey.close()
        tray.hide()
        overlay.hide()
        window.allow_close = True
        history.close()
        lock.unlock()
        app.quit()

    window.quit_callback = quit_app
    quit_action.triggered.connect(quit_app)
    controller.ready_to_quit.connect(finish)
    app.aboutToQuit.connect(hotkey.close)
    if not args.tray:
        window.show()
    window.update_state(controller.state.value, controller.message)
    if args.smoke_test:
        directory.joinpath("screenshots").mkdir(exist_ok=True)

        def capture(index=0):
            window.navigate(index)
            QTimer.singleShot(150, lambda: save(index))

        def save(index):
            window.grab().save(str(directory / "screenshots" / f"page-{index}.png"))
            if index < 3:
                capture(index + 1)
            else:
                controller.shutdown()

        if args.load_model:

            def model_ready(state, message):
                if state in ("idle", "error"):
                    (directory / "smoke-result.json").write_text(
                        json.dumps({"state": state, "message": message}, ensure_ascii=False), encoding="utf-8"
                    )
                    QTimer.singleShot(300, capture)

            controller.changed.connect(model_ready)
            QTimer.singleShot(50, controller.load)
        else:
            QTimer.singleShot(600, capture)
    else:
        QTimer.singleShot(50, controller.load)
    result = app.exec()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
