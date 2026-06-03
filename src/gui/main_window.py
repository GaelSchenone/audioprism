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

        self.panel = ConfigPanel(controller, sources)
        self.preview = GLViewport(controller)
        controller.register_viewport(self.preview)

        layout.addWidget(self.panel)
        layout.addWidget(self.preview, stretch=1)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self._fullscreen: FullscreenWindow | None = None

        self.panel.fullscreen_requested.connect(self.open_fullscreen)
        self.panel.ui_theme_changed.connect(self.apply_ui_theme)
        controller.tick.connect(self._update_status)

        self.apply_ui_theme(controller.settings.ui_theme)

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
        if self._fullscreen:
            self._fullscreen.close()
        self.controller.stop()
        self.preview.release()
        super().closeEvent(event)
