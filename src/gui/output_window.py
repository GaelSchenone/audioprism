"""Detachable output window: a normal, draggable window showing the live
visualization. Drag it to any monitor, then double-click (or F / F11) to go
fullscreen there. Esc leaves fullscreen, or closes the window if windowed."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.gui.viewport import GLViewport


class OutputWindow(QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("audioprism — output  (double-click for fullscreen)")
        self.resize(960, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.viewport = GLViewport(controller)
        layout.addWidget(self.viewport)
        controller.register_viewport(self.viewport)

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def mouseDoubleClickEvent(self, event) -> None:
        self._toggle_fullscreen()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_F, Qt.Key_F11):
            self._toggle_fullscreen()
        elif event.key() == Qt.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.controller.unregister_viewport(self.viewport)
        self.viewport.release()
        super().closeEvent(event)
