"""Main editor window: sidebar + config panel + preview viewport + status bar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStatusBar,
    QWidget,
)

from src.audio.pipewire import AudioSource
from src.gui.config_panel import ConfigPanel
from src.gui.config_window import ConfigWindow
from src.gui.controller import Controller
from src.gui.options_flyout import OptionsFlyout
from src.gui.output_window import OutputWindow
from src.gui.sidebar import Sidebar
from src.gui.viewport import GLViewport


class MainWindow(QMainWindow):
    def __init__(self, controller: Controller, sources: list[AudioSource]) -> None:
        super().__init__()
        self.controller = controller
        self.sources = sources
        self.setWindowTitle("audioprism")
        self.resize(1100, 640)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.sidebar = Sidebar()
        self.panel = ConfigPanel(controller)
        self.preview = GLViewport(controller)
        controller.register_viewport(self.preview)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.panel)
        layout.addWidget(self.preview, stretch=1)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self._output: OutputWindow | None = None
        self._flyout: OptionsFlyout | None = None
        self._config: ConfigWindow | None = None

        self.sidebar.options_clicked.connect(self.toggle_flyout)
        self.sidebar.output_clicked.connect(self.open_output)
        self.sidebar.reset_clicked.connect(self.reset_view)
        controller.tick.connect(self._update_status)

        self._install_shortcuts()
        self.apply_ui_theme(controller.settings.ui_theme)

    # ── keyboard shortcuts ──
    def _install_shortcuts(self) -> None:
        for d in range(10):
            QShortcut(QKeySequence(str(d)), self).activated.connect(
                lambda d=d: self._select_preset_digit(d)
            )
        QShortcut(QKeySequence("Tab"), self).activated.connect(lambda: self._cycle_preset(1))
        QShortcut(QKeySequence("Shift+Tab"), self).activated.connect(lambda: self._cycle_preset(-1))
        QShortcut(QKeySequence(Qt.Key_Space), self).activated.connect(self._toggle_pause)
        QShortcut(QKeySequence("F"), self).activated.connect(self.open_output)
        QShortcut(QKeySequence("R"), self).activated.connect(self.reset_view)

    def reset_view(self) -> None:
        self.controller.camera.reset()
        self.controller.refresh()

    def _select_preset_digit(self, d: int) -> None:
        idx = 9 if d == 0 else d - 1
        if 0 <= idx < self.panel.preset.count():
            self.panel.preset.setCurrentIndex(idx)

    def _cycle_preset(self, step: int) -> None:
        combo = self.panel.preset
        combo.setCurrentIndex((combo.currentIndex() + step) % combo.count())

    def _toggle_pause(self) -> None:
        self.controller.toggle_pause()
        if self.controller.paused:
            self.statusBar().showMessage("⏸ paused — Space to resume")

    # ── options flyout ──
    def toggle_flyout(self) -> None:
        if self._flyout is None:
            self._flyout = OptionsFlyout(self.controller, self)
            self._flyout.config_requested.connect(self.open_config)
        if self._flyout.isVisible():
            self._flyout.hide()
            return
        btn = self.sidebar.options_btn
        pos = btn.mapToGlobal(btn.rect().topRight())
        self._flyout.adjustSize()
        self._flyout.move(pos.x() + 6, pos.y())
        self._flyout.show()

    def open_config(self) -> None:
        if self._config is None:
            self._config = ConfigWindow(self.controller, self.sources, self)
            self._config.ui_theme_changed.connect(self.apply_ui_theme)
        self._config.show()
        self._config.raise_()
        self._config.activateWindow()

    def apply_ui_theme(self, name: str) -> None:
        qss = self.controller.registry.get_ui(name).qss()
        QApplication.instance().setStyleSheet(qss)

    # ── output window ──
    def open_output(self) -> None:
        if self._output is not None:
            self._output.raise_()
            self._output.activateWindow()
            return
        self._output = OutputWindow(self.controller)
        self._output.destroyed.connect(self._on_output_closed)
        self._output.show()

    def _on_output_closed(self, *_) -> None:
        self._output = None

    # ── status ──
    def _update_status(self) -> None:
        c = self.controller
        if c.video_error and c.settings.preset in ("ascii_cam", "point_cloud_cam", "depth"):
            self.statusBar().showMessage(f"⚠ camera: {c.video_error}")
            return
        if c.depth is not None and c.latest_depth is not None:
            self.statusBar().showMessage(f"depth: {c.depth.model}  {c.depth_fps:.1f} fps")
            return
        if c.audio_error:
            self.statusBar().showMessage(f"⚠ audio {c.audio_error} — pick another Source")
            return
        a = c.latest_audio
        if a is None:
            self.statusBar().showMessage("waiting for audio…")
            return
        beat = "  ● BEAT" if a.beat else ""
        bpm = f"  {a.bpm:.0f} BPM" if a.bpm else ""
        self.statusBar().showMessage(
            f"vol {a.volume:.2f}   bass {a.bands['bass']:.2f}   "
            f"mid {a.bands['mid']:.2f}   high {a.bands['high']:.2f}{bpm}{beat}"
        )

    def closeEvent(self, event) -> None:
        self.controller.settings.save()
        if self._flyout:
            self._flyout.close()
        if self._config:
            self._config.close()
        if self._output:
            self._output.close()
        self.controller.stop_all()
        self.preview.release()
        super().closeEvent(event)
