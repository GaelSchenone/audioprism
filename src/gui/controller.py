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
from src.camera3d import Camera3D
from src.engine import VIDEO_PRESETS, DEPTH_PRESETS
from src.video.capture import VideoSource
from src.video.depth import DepthWorker


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
        self.latest_frame = None
        self.latest_depth = None
        self.depth_fps = 0.0
        self.audio_error: str | None = None
        self.video_error: str | None = None
        self.video: VideoSource | None = None
        self.depth: DepthWorker | None = None
        self.camera = Camera3D()             # shared orbit camera for 3D presets
        self.paused = False
        self._viewports: list = []

        self.capture: AudioCapture | None = None
        self.analyzer: AudioAnalyzer | None = None
        if device_index is not None:
            self._open_capture(device_index)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)

    # ── capture lifecycle ──────────────────────────────────────────────────────
    def _open_capture(self, device_index: int) -> None:
        try:
            self.capture = AudioCapture(device=device_index)
            self.analyzer = AudioAnalyzer(sample_rate=self.capture.sample_rate)
            self.settings.source_index = device_index
            self.audio_error = None
        except Exception as e:  # noqa: BLE001 — surface device errors, don't crash
            self.capture = None
            self.analyzer = None
            self.audio_error = f"open failed: {e}"

    def set_source(self, device_index: int) -> None:
        if self.capture:
            self.capture.stop()
        self._open_capture(device_index)
        if self.capture:
            try:
                self.capture.start()
            except Exception as e:  # noqa: BLE001
                self.audio_error = f"start failed: {e}"

    def start(self) -> None:
        if self.capture:
            try:
                self.capture.start()
            except Exception as e:  # noqa: BLE001 — keep the GUI alive on audio failure
                self.audio_error = f"start failed: {e}"
        self._sync_sources(self.settings.preset)
        self.timer.start(max(1, int(1000 / self.settings.fps)))

    # ── video / depth lifecycle ─────────────────────────────────────────────────
    def _sync_sources(self, preset: str) -> None:
        needs_depth = preset in DEPTH_PRESETS
        needs_cam = needs_depth or preset in VIDEO_PRESETS
        if not needs_depth:
            self._release_depth()
        if needs_cam:
            self._ensure_video()
        else:
            self._release_video()
        if needs_depth:
            self._ensure_depth()

    def _ensure_video(self) -> None:
        if self.video is not None:
            return
        self.video = VideoSource(self.settings.video_source)
        if not self.video.start():
            self.video_error = self.video.error
            self.video = None

    def _release_video(self) -> None:
        if self.video is not None:
            self.video.stop()
            self.video = None
        self.latest_frame = None
        self.video_error = None

    def _ensure_depth(self) -> None:
        if self.depth is not None or self.video is None:
            return
        self.depth = DepthWorker(
            lambda: self.video.read() if self.video else None,
            model=self.settings.depth_model,
        )
        self.depth.start()

    def _release_depth(self) -> None:
        if self.depth is not None:
            self.depth.stop()
            self.depth = None
        self.latest_depth = None
        self.depth_fps = 0.0

    def set_video_source(self, spec: int | str) -> None:
        self.settings.video_source = spec
        self._release_depth()
        self._release_video()
        self._sync_sources(self.settings.preset)

    def set_depth_model(self, model: str) -> None:
        self.settings.depth_model = model
        if self.depth is not None:
            self.depth.set_model(model)

    def stop(self) -> None:
        self.timer.stop()
        if self.capture:
            self.capture.stop()

    # ── viewports ──────────────────────────────────────────────────────────────
    def refresh(self) -> None:
        """Repaint all viewports immediately (e.g. after a view reset while paused)."""
        for vp in self._viewports:
            vp.update()

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
        self._sync_sources(name)

    # ── per-frame ──────────────────────────────────────────────────────────────
    def set_fps(self, fps: int) -> None:
        self.settings.fps = fps
        if self.timer.isActive():
            self.timer.start(max(1, int(1000 / fps)))

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            self.timer.stop()
        else:
            self.timer.start(max(1, int(1000 / self.settings.fps)))

    def _on_tick(self) -> None:
        if self.capture and self.analyzer:
            self.analyzer.smoothing = self.settings.smoothing
            samples = self.capture.read()
            if samples is not None:
                self.latest_audio = self.analyzer.analyze(samples)
        if self.video is not None:
            self.latest_frame = self.video.read()
        if self.depth is not None:
            self.latest_depth, self.depth_fps = self.depth.read()
        for vp in self._viewports:
            vp.update()
        self.tick.emit()

    def stop_all(self) -> None:
        self.stop()
        self._release_depth()
        self._release_video()
