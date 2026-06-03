"""Side configuration panel: source, preset, UI theme, graphics palette, sliders."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.audio.pipewire import AudioSource
from src.gui.controller import Controller


def _slider(value: float, lo: float = 0.0, hi: float = 1.0) -> QSlider:
    s = QSlider(Qt.Horizontal)
    s.setMinimum(0)
    s.setMaximum(100)
    s.setValue(int((value - lo) / (hi - lo) * 100))
    s._lo, s._hi = lo, hi  # type: ignore[attr-defined]
    return s


def _slider_value(s: QSlider) -> float:
    return s._lo + (s.value() / 100.0) * (s._hi - s._lo)  # type: ignore[attr-defined]


class ConfigPanel(QWidget):
    fullscreen_requested = Signal()
    ui_theme_changed = Signal(str)

    def __init__(self, controller: Controller, sources: list[AudioSource]) -> None:
        super().__init__()
        self.controller = controller
        self.sources = sources
        self.setFixedWidth(280)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        settings = controller.settings
        reg = controller.registry

        # ── Source ──
        src_box = QGroupBox("Source")
        src_lay = QVBoxLayout(src_box)
        self.source_combo = QComboBox()
        for s in sources:
            self.source_combo.addItem(str(s), s.device_index)
        idx = next((i for i, s in enumerate(sources)
                    if s.device_index == settings.source_index), 0)
        self.source_combo.setCurrentIndex(idx)
        self.source_combo.currentIndexChanged.connect(self._on_source)
        src_lay.addWidget(self.source_combo)
        layout.addWidget(src_box)

        # ── Visual ──
        vis_box = QGroupBox("Visual")
        vis_lay = QVBoxLayout(vis_box)

        vis_lay.addWidget(QLabel("Preset"))
        self.preset_combo = QComboBox()
        from src.engine import PRESET_NAMES
        self.preset_combo.addItems(PRESET_NAMES)
        self.preset_combo.setCurrentText(settings.preset)
        self.preset_combo.currentTextChanged.connect(controller.set_preset)
        vis_lay.addWidget(self.preset_combo)

        vis_lay.addWidget(QLabel("Graphics palette"))
        self.palette_combo = QComboBox()
        self.palette_combo.addItems(reg.palette_names())
        self.palette_combo.setCurrentText(settings.graphics_palette)
        self.palette_combo.currentTextChanged.connect(controller.set_palette)
        vis_lay.addWidget(self.palette_combo)

        vis_lay.addWidget(QLabel("UI theme"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(reg.ui_names())
        self.theme_combo.setCurrentText(settings.ui_theme)
        self.theme_combo.currentTextChanged.connect(self._on_ui_theme)
        vis_lay.addWidget(self.theme_combo)
        layout.addWidget(vis_box)

        # ── Tuning ──
        tune_box = QGroupBox("Tuning")
        tune_lay = QVBoxLayout(tune_box)
        tune_lay.addWidget(QLabel("Sensitivity"))
        self.sens = _slider(settings.sensitivity, 0.1, 4.0)
        self.sens.valueChanged.connect(self._on_sens)
        tune_lay.addWidget(self.sens)
        tune_lay.addWidget(QLabel("Glow / bloom"))
        self.bloom = _slider(settings.bloom, 0.0, 1.0)
        self.bloom.valueChanged.connect(self._on_bloom)
        tune_lay.addWidget(self.bloom)
        layout.addWidget(tune_box)

        # ── Fullscreen ──
        self.fs_btn = QPushButton("Fullscreen  ⛶")
        self.fs_btn.clicked.connect(self.fullscreen_requested.emit)
        layout.addWidget(self.fs_btn)

        layout.addStretch(1)

    # ── handlers ──
    def _on_source(self, i: int) -> None:
        self.controller.set_source(self.source_combo.itemData(i))

    def _on_ui_theme(self, name: str) -> None:
        self.controller.settings.ui_theme = name
        self.ui_theme_changed.emit(name)

    def _on_sens(self) -> None:
        self.controller.settings.sensitivity = _slider_value(self.sens)

    def _on_bloom(self) -> None:
        self.controller.settings.bloom = _slider_value(self.bloom)
