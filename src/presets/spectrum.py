"""Spectrum preset: log-frequency bars colored by the palette, with glow."""

from __future__ import annotations

import numpy as np
import moderngl

from src.audio.analyzer import AudioData
from src.config.settings import VisualizerSettings
from src.presets.base import Preset, fullscreen_vao
from src.presets.bars import make_log_bins, bars_from_spectrum

_VERT = """
#version 330
in vec2 in_pos;
out vec2 v_uv;
void main() {
    v_uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

_FRAG = """
#version 330
in vec2 v_uv;
out vec4 frag;
uniform sampler2D bars;      // width=NBARS, height=1, R = bar magnitude 0..1
uniform sampler2D palette;   // 256x1 gradient LUT
uniform vec3 bg;
uniform float glow;
uniform float mirror;        // 0 = normal, 1 = mirrored from center
void main() {
    float x = mirror > 0.5 ? abs(v_uv.x * 2.0 - 1.0) : v_uv.x;
    float y = v_uv.y;
    float mag = texture(bars, vec2(x, 0.5)).r;
    vec3 barcol = texture(palette, vec2(x, 0.5)).rgb;

    float lit = smoothstep(mag, mag - 0.015, y);          // 1 below the bar top
    float above = max(0.0, y - mag);
    float g = exp(-above * 180.0) * glow;                 // soft glow above the bar
    float shade = mix(0.55, 1.0, (mag > 0.0) ? y / max(mag, 1e-3) : 0.0);

    vec3 col = mix(bg, barcol * shade, lit) + barcol * g * 0.5;
    frag = vec4(col, 1.0);
}
"""


class Spectrum(Preset):
    name = "spectrum"
    NBARS = 128
    FMIN = 30.0
    FMAX = 16000.0

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.vao = fullscreen_vao(ctx, self.prog)
        self.bar_tex = ctx.texture((self.NBARS, 1), 1, dtype="f4")
        self.bar_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.bar_tex.repeat_x = False
        self._idx: np.ndarray | None = None
        self._freqs_len = -1

    def _ensure_bins(self, freqs: np.ndarray) -> None:
        if self._freqs_len == len(freqs):
            return
        self._idx = make_log_bins(freqs, self.NBARS, self.FMIN, self.FMAX)
        self._freqs_len = len(freqs)

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        self._ensure_bins(audio.frequencies)
        bars = bars_from_spectrum(audio.spectrum, self._idx)
        bars = np.clip(bars * settings.sensitivity, 0.0, 1.0).astype("f4")
        self.bar_tex.write(np.ascontiguousarray(bars).tobytes())

        palette_lut.use(0)
        self.bar_tex.use(1)
        self.prog["palette"] = 0
        self.prog["bars"] = 1
        self.prog["bg"] = tuple(background)
        self.prog["glow"] = 0.25      # soft bar tops; global bloom adds the halo
        self.prog["mirror"] = 1.0 if settings.spectrum_mirror else 0.0
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        self.bar_tex.release()
        self.vao.release()
        self.prog.release()
