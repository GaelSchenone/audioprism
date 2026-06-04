"""Configuración window (opened from the ⚙ flyout): UI personalization + audio.

Per-effect, rendering and camera controls live in the main panel; this window
holds the broader configuration: interface theme and audio behavior.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.audio.pipewire import AudioSource
from src.gui.controller import Controller
from src.gui.widgets import bind_slider


class ConfigWindow(QDialog):
    ui_theme_changed = Signal(str)

    def __init__(self, controller: Controller, sources: list[AudioSource], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("audioprism — configuración")
        self.resize(320, 360)
        self.controller = controller
        s = controller.settings
        reg = controller.registry

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # ── Interface ──
        g = QGroupBox("Interface")
        gl = QVBoxLayout(g)
        gl.addWidget(QLabel("UI theme"))
        self.theme = QComboBox()
        self.theme.addItems(reg.ui_names())
        self.theme.setCurrentText(s.ui_theme)
        self.theme.currentTextChanged.connect(self._on_theme)
        gl.addWidget(self.theme)
        lay.addWidget(g)

        # ── Audio ──
        g = QGroupBox("Audio")
        gl = QVBoxLayout(g)
        gl.addWidget(QLabel("Source"))
        self.source = QComboBox()
        for src in sources:
            self.source.addItem(str(src), src.device_index)
        i = next((k for k, src in enumerate(sources) if src.device_index == s.source_index), 0)
        self.source.setCurrentIndex(i)
        self.source.currentIndexChanged.connect(
            lambda k: controller.set_source(self.source.itemData(k))
        )
        gl.addWidget(self.source)
        gl.addWidget(bind_slider(s, "Sensitivity", 0.1, 4.0, "sensitivity"))
        gl.addWidget(bind_slider(s, "Smoothing", 0.0, 0.95, "smoothing"))
        gl.addWidget(QLabel("FPS"))
        self.fps = QComboBox()
        for f in (30, 60, 120):
            self.fps.addItem(str(f), f)
        self.fps.setCurrentText(str(s.fps))
        self.fps.currentIndexChanged.connect(lambda k: controller.set_fps(self.fps.itemData(k)))
        gl.addWidget(self.fps)
        lay.addWidget(g)

        lay.addStretch(1)

        btns = QHBoxLayout()
        save = QPushButton("Save")
        save.clicked.connect(lambda: controller.settings.save())
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        btns.addWidget(save)
        btns.addWidget(close)
        lay.addLayout(btns)

    def _on_theme(self, name: str) -> None:
        self.controller.settings.ui_theme = name
        self.ui_theme_changed.emit(name)
