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
from src.presets.base import Preset
from src.presets.matrix import Matrix
from src.presets.particles import Particles
from src.presets.radial import Radial
from src.presets.spectrum import Spectrum
from src.presets.waveform import Waveform

_LUT_SIZE = 256
_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


PRESET_CLASSES: tuple[type[Preset], ...] = (
    Spectrum, Waveform, Particles, Radial, Matrix,
)
PRESET_NAMES: list[str] = [c.name for c in PRESET_CLASSES]


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

    def _build_targets(self) -> None:
        # Scene is HDR (f2) so bright ink blooms; output is u8 (f1) for display.
        self.scene_texture = self.ctx.texture((self.width, self.height), 4, dtype="f2")
        self.scene_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.scene_fbo = self.ctx.framebuffer(color_attachments=[self.scene_texture])

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
        for obj in (self.scene_fbo, self.scene_texture,
                    self.output_fbo, self.output_texture):
            obj.release()
        self._build_targets()
        self.post.resize((width, height))

    # ── per-frame render ────────────────────────────────────────────────────────
    def render(self, audio: AudioData | None) -> None:
        bg = self.palette.background

        # 1) Scene pass → HDR scene texture
        self.scene_fbo.use()
        self.ctx.viewport = (0, 0, self.width, self.height)
        self.ctx.clear(bg[0], bg[1], bg[2], 1.0)
        if audio is not None:
            self.active.render(audio, self.settings, self.palette_lut, bg)

        # 2) Bloom + composite → output texture
        bg_lum = float(np.array(bg, dtype=np.float32) @ _LUMA)
        self.post.run(self.scene_texture, self.output_fbo,
                      float(self.settings.bloom) * 1.6, bg_lum)

    def release(self) -> None:
        for preset in self.presets.values():
            preset.release()
        self.post.release()
        self.palette_lut.release()
        for obj in (self.scene_fbo, self.scene_texture,
                    self.output_fbo, self.output_texture):
            obj.release()
