"""Separate fullscreen window (multi-monitor) showing the live visualization."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.gui.viewport import GLViewport


class FullscreenWindow(QWidget):
    def __init__(self, controller, screen: QScreen | None = None) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("audioprism — fullscreen")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.viewport = GLViewport(controller)
        layout.addWidget(self.viewport)

        controller.register_viewport(self.viewport)

        if screen is not None:
            self.setScreen(screen)
            self.setGeometry(screen.geometry())

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Escape, Qt.Key_F11, Qt.Key_F):
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.controller.unregister_viewport(self.viewport)
        self.viewport.release()
        super().closeEvent(event)
