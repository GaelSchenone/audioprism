"""Small dropdown flyout from the sidebar ⚙ button: Configuración + Save."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout

from src.gui.controller import Controller


class OptionsFlyout(QFrame):
    config_requested = Signal()

    def __init__(self, controller: Controller, parent=None) -> None:
        super().__init__(parent, Qt.Popup)
        self.controller = controller
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedWidth(170)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        config = QPushButton("⚙  Configuración")
        config.clicked.connect(self._open_config)
        layout.addWidget(config)

        save = QPushButton("💾  Save")
        save.clicked.connect(self._save)
        layout.addWidget(save)

    def _open_config(self) -> None:
        self.hide()
        self.config_requested.emit()

    def _save(self) -> None:
        self.controller.settings.save()
        self.hide()
