"""VisualizerEngine: owns the GL render targets, palette LUT, and presets.

Renders the active preset into an offscreen RGBA framebuffer (output_fbo). Both
the editor preview and the fullscreen window sample output_texture, so the
visualization is computed once and displayed in multiple windows.
"""

from __future__ import annotations

import numpy as np
import moderngl

from src.audio.analyzer import AudioData
from src.config.settings import VisualizerSettings
from src.config.theme import Palette
from src.postprocess import PostProcess
from src.presets.ascii_bars import AsciiBars
from src.presets.ascii_cam import AsciiCam
from src.presets.base import Preset
from src.presets.depth_view import Depth
from src.presets.matrix import Matrix
from src.presets.particles import Particles
from src.presets.point_cloud_audio import PointCloudAudio
from src.presets.point_cloud_cam import PointCloudCam
from src.presets.radial import Radial
from src.presets.spectrum import Spectrum
from src.presets.waveform import Waveform

_LUT_SIZE = 256
_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def _silent_audio() -> AudioData:
    """A zero AudioData so presets still render when no audio is available."""
    freqs = np.fft.rfftfreq(2048, 1.0 / 48000).astype(np.float32)
    return AudioData(
        waveform=np.zeros(2048, "f4"),
        spectrum=np.zeros(len(freqs), "f4"),
        frequencies=freqs,
        bands={k: 0.0 for k in ("sub_bass", "bass", "mid", "high_mid", "high")},
        volume=0.0,
        beat=False,
        bpm=0.0,
    )


PRESET_CLASSES: tuple[type[Preset], ...] = (
    Spectrum, Waveform, Particles, Radial, Matrix, AsciiBars, AsciiCam, Depth,
    PointCloudAudio, PointCloudCam,
)
PRESET_NAMES: list[str] = [c.name for c in PRESET_CLASSES]
VIDEO_PRESETS: set[str] = {c.name for c in PRESET_CLASSES if c.needs_video}
DEPTH_PRESETS: set[str] = {c.name for c in PRESET_CLASSES if c.needs_depth}
PRESET_PARAMS: dict[str, tuple[str, ...]] = {c.name: c.params for c in PRESET_CLASSES}
PRESET_NEEDS_CAMERA: set[str] = VIDEO_PRESETS | DEPTH_PRESETS


def _build_presets(ctx: moderngl.Context) -> dict[str, Preset]:
    return {c.name: c(ctx) for c in PRESET_CLASSES}


class VisualizerEngine:
    def __init__(
        self,
        ctx: moderngl.Context,
        size: tuple[int, int],
        palette: Palette,
        settings: VisualizerSettings,
    ) -> None:
        self.ctx = ctx
        self.width, self.height = size
        self.settings = settings

        self._build_targets()
        self.post = PostProcess(ctx, (self.width, self.height))

        self.palette_lut = ctx.texture((_LUT_SIZE, 1), 3, dtype="f4")
        self.palette_lut.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.palette_lut.repeat_x = False
        self.set_palette(palette)

        self.presets = _build_presets(ctx)
        self.active = self.presets.get(settings.preset) or next(iter(self.presets.values()))
        self._silent = _silent_audio()
        self.camera = None        # set by the viewport (shared Camera3D) for 3D presets

    def _build_targets(self) -> None:
        # Scene is HDR (f2) so bright ink blooms; output is u8 (f1) for display.
        # A depth buffer lets 3D point-cloud presets occlude correctly.
        self.scene_texture = self.ctx.texture((self.width, self.height), 4, dtype="f2")
        self.scene_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.scene_depth = self.ctx.depth_renderbuffer((self.width, self.height))
        self.scene_fbo = self.ctx.framebuffer(
            color_attachments=[self.scene_texture], depth_attachment=self.scene_depth
        )

        self.output_texture = self.ctx.texture((self.width, self.height), 4, dtype="f1")
        self.output_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.output_fbo = self.ctx.framebuffer(color_attachments=[self.output_texture])

    # ── configuration ─────────────────────────────────────────────────────────
    def set_palette(self, palette: Palette) -> None:
        self.palette = palette
        lut = palette.to_lut(_LUT_SIZE).astype("f4")          # (256, 3)
        self.palette_lut.write(np.ascontiguousarray(lut).tobytes())

    def set_preset(self, name: str) -> None:
        if name in self.presets:
            self.active = self.presets[name]

    def preset_names(self) -> list[str]:
        return list(self.presets)

    def resize(self, width: int, height: int) -> None:
        if (width, height) == (self.width, self.height) or width <= 0 or height <= 0:
            return
        self.width, self.height = width, height
        for obj in (self.scene_fbo, self.scene_texture, self.scene_depth,
                    self.output_fbo, self.output_texture):
            obj.release()
        self._build_targets()
        self.post.resize((width, height))

    # ── per-frame render ────────────────────────────────────────────────────────
    def render(self, audio: AudioData | None, frame=None, depth=None) -> None:
        dim = self.settings.background_dim
        bg = tuple(c * dim for c in self.palette.background)
        a = audio if audio is not None else self._silent

        # 1) Scene pass → HDR scene texture
        self.scene_fbo.use()
        self.ctx.viewport = (0, 0, self.width, self.height)
        self.ctx.clear(bg[0], bg[1], bg[2], 1.0)
        if hasattr(self.active, "set_frame"):
            self.active.set_frame(frame)
        if hasattr(self.active, "set_depth"):
            self.active.set_depth(depth)
        if hasattr(self.active, "set_mvp") and self.camera is not None:
            self.active.set_mvp(self.camera.mvp(self.width / self.height))
        self.active.render(a, self.settings, self.palette_lut, bg)

        # 2) Bloom + composite → output texture
        bg_lum = float(np.array(bg, dtype=np.float32) @ _LUMA)
        self.post.run(self.scene_texture, self.output_fbo,
                      float(self.settings.bloom) * 1.6, bg_lum)

    def capture_output(self) -> np.ndarray | None:
        """Return the current output texture as (H, W, 4) uint8 RGBA, or None."""
        try:
            self.output_fbo.use()
            data = self.ctx.read_pixels(
                0, 0, self.width, self.height, components=4, dtype="f1"
            )
            return np.frombuffer(data, dtype=np.uint8).reshape(self.height, self.width, 4)
        except Exception:
            return None

    def release(self) -> None:
        for preset in self.presets.values():
            preset.release()
        self.post.release()
        self.palette_lut.release()
        for obj in (self.scene_fbo, self.scene_texture, self.scene_depth,
                    self.output_fbo, self.output_texture):
            if obj is not None:
                obj.release()
        # Null everything so a double-release is safe
        self.scene_fbo = None
        self.scene_texture = None
        self.scene_depth = None
        self.output_fbo = None
        self.output_texture = None
        self.palette_lut = None
