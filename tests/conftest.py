import time

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    return application


@pytest.fixture
def wait(app):
    def until(predicate, timeout=5):
        end = time.monotonic() + timeout
        while not predicate():
            app.processEvents()
            if time.monotonic() > end:
                raise AssertionError("Timed out waiting for event")
            time.sleep(0.005)
        app.processEvents()

    return until
