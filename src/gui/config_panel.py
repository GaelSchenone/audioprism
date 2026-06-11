"""Main panel beside the preview: shows only the controls relevant to the
active preset. Preset params appear/disappear with the effect; the Camera/Depth
group only shows for camera-based presets. Audio/interface options live in the
⚙ flyout on the sidebar."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.engine import PRESET_NAMES, PRESET_PARAMS, PRESET_NEEDS_CAMERA
from src.gui.controller import Controller
from src.gui.palette_editor import GradientSwatch, PaletteEditor
from src.gui.widgets import bind_slider
from src.video.capture import list_cameras
from src.video.depth import MODELS as DEPTH_MODELS

# param field → (label, lo, hi, integer)
_PARAM_SPECS = [
    ("particle_count", "Particle count", 500, 60000, True),
    ("matrix_density", "Matrix density", 16, 160, True),
    ("ascii_grid", "ASCII grid", 16, 220, True),
    ("point_size", "Point size", 0.3, 4.0, False),
]


class ConfigPanel(QWidget):
    def __init__(self, controller: Controller) -> None:
        super().__init__()
        self.controller = controller
        self.setFixedWidth(244)
        s = controller.settings
        reg = controller.registry

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setSpacing(10)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        # ── Visualizer (always shown) ──
        g = QGroupBox("Visualizer")
        gl = QVBoxLayout(g)
        gl.addWidget(QLabel("Preset"))
        self.preset = QComboBox()
        self.preset.addItems(PRESET_NAMES)
        self.preset.setCurrentText(s.preset)
        self.preset.currentTextChanged.connect(controller.set_preset)
        self.preset.currentTextChanged.connect(self._apply_preset)
        gl.addWidget(self.preset)
        gl.addWidget(QLabel("Graphics palette"))
        self.palette = QComboBox()
        self.palette.addItems(reg.palette_names())
        self.palette.setCurrentText(s.graphics_palette)
        self.palette.currentTextChanged.connect(controller.set_palette)
        self.palette.currentTextChanged.connect(self._update_swatch)
        gl.addWidget(self.palette)
        self.swatch = GradientSwatch(reg.get_palette(s.graphics_palette))
        gl.addWidget(self.swatch)
        edit = QPushButton("Edit / new palette…")
        edit.clicked.connect(self._open_palette_editor)
        gl.addWidget(edit)
        lay.addWidget(g)

        # ── Effect parameters (per-preset, shown/hidden) ──
        self.param_group = QGroupBox("Effect")
        gl = QVBoxLayout(self.param_group)
        self.param_widgets: dict[str, QWidget] = {}
        for field, label, lo, hi, integer in _PARAM_SPECS:
            w = bind_slider(s, label, lo, hi, field, integer=integer)
            self.param_widgets[field] = w
            gl.addWidget(w)
        lay.addWidget(self.param_group)

        # ── Rendering (always shown) ──
        g = QGroupBox("Rendering")
        gl = QVBoxLayout(g)
        gl.addWidget(bind_slider(s, "Glow / bloom", 0.0, 1.0, "bloom"))
        gl.addWidget(bind_slider(s, "Background dim", 0.0, 1.0, "background_dim"))
        lay.addWidget(g)

        # ── Camera / Depth (only for camera presets) ──
        self.camera_group = QGroupBox("Camera / Depth")
        gl = QVBoxLayout(self.camera_group)
        gl.addWidget(QLabel("Camera"))
        self.cam = QComboBox()
        cameras = list_cameras()
        if cameras:
            for idx in cameras:
                self.cam.addItem(f"Camera {idx}", idx)
            if isinstance(s.video_source, int) and s.video_source in cameras:
                self.cam.setCurrentIndex(cameras.index(s.video_source))
        else:
            self.cam.addItem("No camera detected", -1)
            self.cam.setEnabled(False)
        self.cam.currentIndexChanged.connect(self._on_camera)
        gl.addWidget(self.cam)
        gl.addWidget(QLabel("Depth model"))
        self.depth = QComboBox()
        for m in DEPTH_MODELS:
            self.depth.addItem(m, m)
        self.depth.setCurrentText(s.depth_model)
        self.depth.currentTextChanged.connect(controller.set_depth_model)
        gl.addWidget(self.depth)
        load_video = QPushButton("Load video file…")
        load_video.clicked.connect(self._load_video)
        gl.addWidget(load_video)
        self.video_label = QLabel(self._video_text())
        self.video_label.setWordWrap(True)
        gl.addWidget(self.video_label)
        lay.addWidget(self.camera_group)

        lay.addStretch(1)
        self._apply_preset(s.preset)

    # ── dynamic visibility ──
    def _apply_preset(self, name: str) -> None:
        params = PRESET_PARAMS.get(name, ())
        any_visible = False
        for field, w in self.param_widgets.items():
            visible = field in params
            w.setVisible(visible)
            any_visible = any_visible or visible
        self.param_group.setVisible(any_visible)
        self.camera_group.setVisible(name in PRESET_NEEDS_CAMERA)

    # ── palette ──
    def _update_swatch(self, name: str) -> None:
        self.swatch.set_palette(self.controller.registry.get_palette(name))

    def _open_palette_editor(self) -> None:
        editor = PaletteEditor(self.controller, self.palette.currentText(), self)
        editor.palette_saved.connect(self._on_palette_saved)
        editor.exec()

    def _on_palette_saved(self, name: str) -> None:
        reg = self.controller.registry
        self.palette.blockSignals(True)
        self.palette.clear()
        self.palette.addItems(reg.palette_names())
        self.palette.blockSignals(False)
        if name:
            self.palette.setCurrentText(name)   # triggers set_palette + swatch

    # ── handlers ──
    def _on_camera(self, _i: int) -> None:
        idx = self.cam.currentData()
        if idx is not None and idx >= 0:
            self.controller.set_video_source(idx)
            self.video_label.setText(self._video_text())

    def _video_text(self) -> str:
        src = self.controller.settings.video_source
        return f"video: {src}" if isinstance(src, str) else f"camera {src}"

    def _load_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a video file", "", "Video (*.mp4 *.avi *.mov *.mkv *.webm)"
        )
        if path:
            self.controller.set_video_source(path)
            self.video_label.setText(self._video_text())
