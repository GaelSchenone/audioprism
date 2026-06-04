"""Settings window: the full configuration page, separate from the main panel.

Every control here applies live (settings are a shared object the engine reads
each frame) and 'Save' persists them to ~/.config/audioprism/settings.json.
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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.audio.pipewire import AudioSource
from src.gui.controller import Controller
from src.gui.widgets import LabeledSlider
from src.video.depth import MODELS as DEPTH_MODELS


class SettingsDialog(QDialog):
    ui_theme_changed = Signal(str)

    def __init__(self, controller: Controller, sources: list[AudioSource], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("audioprism — settings")
        self.resize(360, 620)
        self.controller = controller
        s = controller.settings
        reg = controller.registry

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setSpacing(10)
        scroll.setWidget(body)
        outer.addWidget(scroll)

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
        gl.addWidget(self._slider("Sensitivity", 0.1, 4.0, s.sensitivity, "sensitivity"))
        gl.addWidget(self._slider("Smoothing", 0.0, 0.95, s.smoothing, "smoothing"))
        gl.addWidget(QLabel("FPS"))
        self.fps = QComboBox()
        for f in (30, 60, 120):
            self.fps.addItem(str(f), f)
        self.fps.setCurrentText(str(s.fps))
        self.fps.currentIndexChanged.connect(lambda k: controller.set_fps(self.fps.itemData(k)))
        gl.addWidget(self.fps)
        lay.addWidget(g)

        # ── Rendering ──
        g = QGroupBox("Rendering")
        gl = QVBoxLayout(g)
        gl.addWidget(self._slider("Glow / bloom", 0.0, 1.0, s.bloom, "bloom"))
        gl.addWidget(self._slider("Background dim", 0.0, 1.0, s.background_dim, "background_dim"))
        lay.addWidget(g)

        # ── Camera / Depth ──
        g = QGroupBox("Camera / Depth")
        gl = QVBoxLayout(g)
        gl.addWidget(QLabel("Camera index"))
        self.cam = QComboBox()
        for idx in range(6):
            self.cam.addItem(f"Camera {idx}", idx)
        if isinstance(s.video_source, int) and s.video_source < 6:
            self.cam.setCurrentIndex(s.video_source)
        self.cam.currentIndexChanged.connect(
            lambda k: controller.set_video_source(self.cam.itemData(k))
        )
        gl.addWidget(self.cam)
        gl.addWidget(QLabel("Depth model"))
        self.depth = QComboBox()
        for m in DEPTH_MODELS:
            self.depth.addItem(m, m)
        self.depth.setCurrentText(s.depth_model)
        self.depth.currentTextChanged.connect(controller.set_depth_model)
        gl.addWidget(self.depth)
        lay.addWidget(g)

        # ── Preset parameters ──
        g = QGroupBox("Preset parameters")
        gl = QVBoxLayout(g)
        gl.addWidget(self._slider("Particle count", 500, 60000, s.particle_count, "particle_count", integer=True))
        gl.addWidget(self._slider("ASCII grid", 16, 220, s.ascii_grid, "ascii_grid", integer=True))
        gl.addWidget(self._slider("Matrix density", 16, 160, s.matrix_density, "matrix_density", integer=True))
        gl.addWidget(self._slider("Point size", 0.3, 4.0, s.point_size, "point_size"))
        lay.addWidget(g)

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

        lay.addStretch(1)

        # ── Buttons ──
        btns = QHBoxLayout()
        save = QPushButton("Save")
        save.clicked.connect(lambda: controller.settings.save())
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        btns.addWidget(save)
        btns.addWidget(close)
        outer.addLayout(btns)

    def _slider(self, label, lo, hi, value, attr, integer=False) -> LabeledSlider:
        s = self.controller.settings
        w = LabeledSlider(label, lo, hi, value, integer=integer)
        cast = int if integer else float
        w.changed.connect(lambda v, a=attr, c=cast: setattr(s, a, c(v)))
        return w

    def _on_theme(self, name: str) -> None:
        self.controller.settings.ui_theme = name
        self.ui_theme_changed.emit(name)
