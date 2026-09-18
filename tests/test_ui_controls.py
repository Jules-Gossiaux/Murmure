from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

from murmure.ui import NoWheelComboBox


def test_selector_consumes_mouse_wheel_without_changing_value(app):
    selector = NoWheelComboBox()
    selector.addItems(["Un", "Deux"])
    selector.setCurrentIndex(0)
    event = QWheelEvent(
        QPointF(4, 4),
        QPointF(4, 4),
        QPoint(0, 120),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    assert selector.event(event)
    assert selector.currentIndex() == 0
