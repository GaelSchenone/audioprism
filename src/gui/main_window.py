"""Main editor window: config panel + preview viewport + status bar."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStatusBar,
    QWidget,
)

from src.audio.pipewire import AudioSource
from src.gui.config_panel import ConfigPanel
from src.gui.controller import Controller
from src.gui.fullscreen import FullscreenWindow
from src.gui.settings_dialog import SettingsDialog
from src.gui.viewport import GLViewport


class MainWindow(QMainWindow):
    def __init__(self, controller: Controller, sources: list[AudioSource]) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("audioprism")
        self.resize(1100, 640)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.sources = sources
        self.panel = ConfigPanel(controller)
        self.preview = GLViewport(controller)
        controller.register_viewport(self.preview)

        layout.addWidget(self.panel)
        layout.addWidget(self.preview, stretch=1)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self._fullscreen: FullscreenWindow | None = None
        self._settings: SettingsDialog | None = None

        self.panel.fullscreen_requested.connect(self.open_fullscreen)
        self.panel.settings_requested.connect(self.open_settings)
        controller.tick.connect(self._update_status)

        self.apply_ui_theme(controller.settings.ui_theme)

    def open_settings(self) -> None:
        if self._settings is None:
            self._settings = SettingsDialog(self.controller, self.sources, self)
            self._settings.ui_theme_changed.connect(self.apply_ui_theme)
        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    def apply_ui_theme(self, name: str) -> None:
        qss = self.controller.registry.get_ui(name).qss()
        QApplication.instance().setStyleSheet(qss)

    def open_fullscreen(self) -> None:
        if self._fullscreen is not None:
            self._fullscreen.activateWindow()
            return
        screens = QApplication.screens()
        target = screens[1] if len(screens) > 1 else screens[0]
        self._fullscreen = FullscreenWindow(self.controller, target)
        self._fullscreen.destroyed.connect(self._on_fullscreen_closed)
        self._fullscreen.showFullScreen()

    def _on_fullscreen_closed(self, *_) -> None:
        self._fullscreen = None

    def _update_status(self) -> None:
        if self.controller.video_error and self.controller.settings.preset in (
            "ascii_cam", "point_cloud_cam", "depth",
        ):
            self.statusBar().showMessage(f"⚠ camera: {self.controller.video_error}")
            return
        if self.controller.depth is not None and self.controller.latest_depth is not None:
            self.statusBar().showMessage(
                f"depth: {self.controller.depth.model}  {self.controller.depth_fps:.1f} fps"
            )
            return
        if self.controller.audio_error:
            self.statusBar().showMessage(
                f"⚠ audio {self.controller.audio_error} — pick another Source"
            )
            return
        a = self.controller.latest_audio
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
        if self._settings:
            self._settings.close()
        if self._fullscreen:
            self._fullscreen.close()
        self.controller.stop_all()
        self.preview.release()
        super().closeEvent(event)
