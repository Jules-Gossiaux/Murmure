"""Capture populated light/dark pages using an isolated, disposable history."""

import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication, QScrollArea

from murmure.controller import Controller, State
from murmure.storage import History, Settings
from murmure.style import apply_theme
from murmure.ui import MainWindow

app = QApplication([])
app.setStyle("Fusion")
app.setQuitOnLastWindowClosed(False)
output = Path("artifacts/revision-visual").resolve()
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    history = History(root)
    identifier, _ = history.begin()
    history.update(
        identifier,
        text="Bonjour, voici une dictée corrigée au clavier.\nLes modifications sont enregistrées automatiquement.",
        audio="",
        status="saved",
        duration=4.4,
        detail="Texte enregistré.",
    )
    controller = Controller(root, Settings(), history)
    controller.state = State.IDLE
    window = MainWindow(controller, root)
    window.update_state("idle", "Prêt à dicter · base · CPU")
    window.show()
    for theme in ("light", "dark"):
        controller.settings.theme = theme
        window.theme.setCurrentIndex(window.theme.findData(theme))
        apply_theme(app, theme)
        for index in (0, 1, 3):
            window.navigate(index)
            app.processEvents()
            window.grab().save(str(output / f"{theme}-{index}.png"))
            if index == 3:
                scroll = window.pages.currentWidget().findChild(QScrollArea)
                scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                app.processEvents()
                window.grab().save(str(output / f"{theme}-settings-bottom.png"))
        window.navigate(0)
        window.resize(880, 640)
        app.processEvents()
        scroll = window.pages.currentWidget()
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        app.processEvents()
        assert window.copy_latest.geometry().top() > window.latest_text.geometry().bottom()
        window.grab().save(str(output / f"{theme}-compact.png"))
        window.resize(1080, 760)
    window.allow_close = True
    window.close()
    controller.engine_pool.shutdown()
    controller.io_pool.shutdown()
    history.close()
print(output)
