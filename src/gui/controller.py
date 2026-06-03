"""Controller: owns audio capture/analysis, shared state, and the frame timer.

Holds the canonical settings + palette. Each GLViewport pulls from here in its
paintGL, so config changes (palette, preset, sliders) need no GL context juggling
on the controller side — they just mutate shared state and bump a version counter.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from src.audio.capture import AudioCapture
from src.audio.analyzer import AudioAnalyzer, AudioData
from src.config.settings import VisualizerSettings
from src.config.theme import ThemeRegistry, Palette


class Controller(QObject):
    tick = Signal()                  # emitted each frame (for status updates)

    def __init__(
        self,
        device_index: int | None,
        settings: VisualizerSettings,
        registry: ThemeRegistry,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.registry = registry
        self.palette: Palette = registry.get_palette(settings.graphics_palette)
        self.palette_version = 0
        self.latest_audio: AudioData | None = None
        self._viewports: list = []

        self.capture: AudioCapture | None = None
        self.analyzer: AudioAnalyzer | None = None
        if device_index is not None:
            self._open_capture(device_index)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)

    # ── capture lifecycle ──────────────────────────────────────────────────────
    def _open_capture(self, device_index: int) -> None:
        self.capture = AudioCapture(device=device_index)
        self.analyzer = AudioAnalyzer(sample_rate=self.capture.sample_rate)
        self.settings.source_index = device_index

    def set_source(self, device_index: int) -> None:
        if self.capture:
            self.capture.stop()
        self._open_capture(device_index)
        self.capture.start()

    def start(self) -> None:
        if self.capture:
            self.capture.start()
        self.timer.start(max(1, int(1000 / self.settings.fps)))

    def stop(self) -> None:
        self.timer.stop()
        if self.capture:
            self.capture.stop()

    # ── viewports ──────────────────────────────────────────────────────────────
    def register_viewport(self, vp) -> None:
        self._viewports.append(vp)

    def unregister_viewport(self, vp) -> None:
        if vp in self._viewports:
            self._viewports.remove(vp)

    # ── config mutations ───────────────────────────────────────────────────────
    def set_palette(self, name: str) -> None:
        self.settings.graphics_palette = name
        self.palette = self.registry.get_palette(name)
        self.palette_version += 1

    def set_preset(self, name: str) -> None:
        self.settings.preset = name

    # ── per-frame ──────────────────────────────────────────────────────────────
    def _on_tick(self) -> None:
        if self.capture and self.analyzer:
            samples = self.capture.read()
            if samples is not None:
                self.latest_audio = self.analyzer.analyze(samples)
        for vp in self._viewports:
            vp.update()
        self.tick.emit()
