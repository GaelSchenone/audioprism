"""Slim main panel: the most-used live controls. Everything else lives in the
Settings window (opened with the ⚙ button)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.engine import PRESET_NAMES
from src.gui.controller import Controller


class ConfigPanel(QWidget):
    fullscreen_requested = Signal()
    settings_requested = Signal()

    def __init__(self, controller: Controller) -> None:
        super().__init__()
        self.controller = controller
        self.setFixedWidth(220)
        s = controller.settings
        reg = controller.registry

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        box = QGroupBox("Visualizer")
        bl = QVBoxLayout(box)
        bl.addWidget(QLabel("Preset"))
        self.preset = QComboBox()
        self.preset.addItems(PRESET_NAMES)
        self.preset.setCurrentText(s.preset)
        self.preset.currentTextChanged.connect(controller.set_preset)
        bl.addWidget(self.preset)

        bl.addWidget(QLabel("Graphics palette"))
        self.palette = QComboBox()
        self.palette.addItems(reg.palette_names())
        self.palette.setCurrentText(s.graphics_palette)
        self.palette.currentTextChanged.connect(controller.set_palette)
        bl.addWidget(self.palette)
        layout.addWidget(box)

        self.settings_btn = QPushButton("⚙  Settings")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)

        self.fs_btn = QPushButton("Fullscreen  ⛶")
        self.fs_btn.clicked.connect(self.fullscreen_requested.emit)
        layout.addWidget(self.fs_btn)

        layout.addStretch(1)
