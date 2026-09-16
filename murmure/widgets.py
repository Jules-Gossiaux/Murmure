from __future__ import annotations

import math
import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget


def app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#365d48"))
    painter.drawRoundedRect(QRectF(0, 0, 64, 64), 17, 17)
    painter.setPen(QPen(QColor("#eef5e8"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for x, height in ((17, 12), (27, 29), (37, 38), (47, 18)):
        painter.drawLine(x, 32 - height // 2, x, 32 + height // 2)
    painter.end()
    return QIcon(pixmap)


class Overlay(QWidget):
    def __init__(self, controller):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.controller = controller
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(360, 72)
        self.state = "idle"
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)
        self.animation = QTimer(self)
        self.animation.setInterval(45)
        self.animation.timeout.connect(self.update)

    def show_state(self, state: str, message: str):
        was_active = self.state in ("recording", "starting", "transcribing", "inserting", "cancelling")
        self.state = state
        self.hide_timer.stop()
        if state in ("starting", "recording", "transcribing", "inserting", "cancelling"):
            if not self.isVisible():
                screen = QApplication.screenAt(QCursor.pos())
                geometry = (screen or QApplication.primaryScreen()).availableGeometry()
                self.move(geometry.center().x() - self.width() // 2, geometry.bottom() - self.height() - 28)
            self.show()
            self.animation.start()
        elif was_active:
            self.hide_timer.start(2000 if state == "error" else 1300)
        else:
            self.hide()
        self.update()

    def hideEvent(self, event):
        self.animation.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#526b58"), 1))
        painter.setBrush(QColor("#253b2e"))
        painter.drawRoundedRect(QRectF(2, 2, 356, 64), 22, 22)
        recording = self.state == "recording"
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f5a58c" if recording else "#bed6ae"))
        painter.drawEllipse(QRectF(23, 28, 9, 9))
        label = {
            "starting": "Ouverture du micro",
            "recording": "À vous de parler",
            "transcribing": "Transcription locale",
            "inserting": "Insertion du texte",
            "cancelling": "Annulation de la dictée",
            "error": "À voir dans l’historique",
            "idle": "Dictée annulée" if "annulée" in self.controller.message else "Dictée terminée",
        }.get(self.state, "Murmure")
        painter.setPen(QColor("#f1f6ec"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        painter.drawText(46, 30, label)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#b3c8aa"))
        elapsed = int(time.monotonic() - self.controller.record_started) if recording else 0
        subtitle = (
            f"{elapsed // 60:02d}:{elapsed % 60:02d}  ·  Échap pour annuler"
            if recording
            else "Votre voix reste sur cet ordinateur"
        )
        painter.drawText(46, 48, subtitle)
        level = self.controller.recorder.level if self.controller.recorder else 0
        painter.setPen(QPen(QColor("#bddaac"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for i in range(7):
            height = 4 + (min(level * 150, 24) if recording else 8) * abs(math.sin(time.monotonic() * 5 + i))
            painter.drawLine(294 + i * 6, int(33 - height / 2), 294 + i * 6, int(33 + height / 2))
        painter.end()
