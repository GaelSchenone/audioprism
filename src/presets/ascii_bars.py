"""ASCII bars preset: frequency bars rendered as typographic ASCII characters."""

from __future__ import annotations

import numpy as np
import moderngl

from src.audio.analyzer import AudioData
from src.ascii_atlas import AsciiAtlas
from src.config.settings import VisualizerSettings
from src.presets.base import Preset, fullscreen_vao
from src.presets.bars import make_log_bins, bars_from_spectrum

_VERT = """
#version 330
in vec2 in_pos;
out vec2 v_uv;
void main() { v_uv = in_pos * 0.5 + 0.5; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

_FRAG = """
#version 330
in vec2 v_uv; out vec4 frag;
uniform sampler2D bars;       // COLS wide, r = magnitude
uniform sampler2D palette;
uniform sampler2D atlas;      // glyph strip, natlas cells wide
uniform vec3 bg;
uniform vec2 grid;            // cols, rows
uniform float natlas;
void main() {
    vec2 cell = floor(v_uv * grid);
    vec2 local = fract(v_uv * grid);

    float x = (cell.x + 0.5) / grid.x;
    float mag = texture(bars, vec2(x, 0.5)).r;
    float cellY = cell.y / grid.y;                       // bottom edge of cell

    // Coverage: 1 if cell fully below the bar top, partial at the top, 0 above
    float cov = clamp((mag - cellY) * grid.y, 0.0, 1.0);
    float gi = floor(cov * (natlas - 1.0) + 0.5);        // glyph index
    float gx = (gi + local.x) / natlas;
    float ink = texture(atlas, vec2(gx, local.y)).r;

    vec3 col = texture(palette, vec2(x, 0.5)).rgb;
    frag = vec4(bg + col * ink * step(0.001, cov), 1.0);
}
"""


class AsciiBars(Preset):
    name = "ascii_bars"
    params = ("ascii_grid",)
    COLS = 64
    FMIN = 30.0
    FMAX = 16000.0

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.vao = fullscreen_vao(ctx, self.prog)
        self.bar_tex = ctx.texture((self.COLS, 1), 1, dtype="f4")
        self.bar_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.bar_tex.repeat_x = False

        self.atlas = AsciiAtlas()
        self.atlas_tex = self.atlas.texture(ctx)
        self._aspect_ratio = self.atlas.cell_w / self.atlas.cell_h
        self._idx: np.ndarray | None = None
        self._freqs_len = -1

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        if self._freqs_len != len(audio.frequencies):
            self._idx = make_log_bins(audio.frequencies, self.COLS, self.FMIN, self.FMAX)
            self._freqs_len = len(audio.frequencies)

        bars = bars_from_spectrum(audio.spectrum, self._idx)
        bars = np.clip(bars * settings.sensitivity, 0.0, 1.0).astype("f4")
        self.bar_tex.write(np.ascontiguousarray(bars).tobytes())

        _, _, w, h = self.ctx.viewport
        aspect = (w / h) if h else 1.0
        rows = max(6.0, round(self.COLS / aspect * self._aspect_ratio))

        palette_lut.use(0)
        self.bar_tex.use(1)
        self.atlas_tex.use(2)
        self.prog["palette"] = 0
        self.prog["bars"] = 1
        self.prog["atlas"] = 2
        self.prog["bg"] = tuple(background)
        self.prog["grid"] = (float(self.COLS), float(rows))
        self.prog["natlas"] = float(self.atlas.n)
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        self.bar_tex.release()
        self.atlas_tex.release()
        self.vao.release()
        self.prog.release()
