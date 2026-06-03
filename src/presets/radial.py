"""Radial preset: the spectrum wrapped into a circle, pulsing with volume."""

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
void main() { v_uv = in_pos * 0.5 + 0.5; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

_FRAG = """
#version 330
#define PI 3.14159265
in vec2 v_uv; out vec4 frag;
uniform sampler2D bars;      // NBARS wide, r = magnitude
uniform sampler2D palette;
uniform vec3 bg;
uniform float aspect;
uniform float volume;
void main() {
    vec2 p = v_uv - 0.5;
    if (aspect > 1.0) p.x *= aspect; else p.y /= aspect;
    float r = length(p) * 2.0;
    float ang = atan(p.y, p.x);
    // Fold angle so the spectrum is mirrored left/right (symmetric ring)
    float a01 = abs(ang) / PI;                  // 0 at right, 1 at left
    float mag = texture(bars, vec2(a01, 0.5)).r;

    float inner = 0.20 + volume * 0.06;         // ring pulses with volume
    float outer = inner + mag * 0.55;
    float band = smoothstep(inner - 0.004, inner + 0.004, r)
               * (1.0 - smoothstep(outer - 0.012, outer + 0.012, r));
    float ring = smoothstep(0.006, 0.0, abs(r - inner));

    vec3 col = texture(palette, vec2(mag, 0.5)).rgb;
    frag = vec4(bg + col * band + col * ring * 0.6, 1.0);
}
"""


class Radial(Preset):
    name = "radial"
    NBARS = 180
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

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        if self._freqs_len != len(audio.frequencies):
            self._idx = make_log_bins(audio.frequencies, self.NBARS, self.FMIN, self.FMAX)
            self._freqs_len = len(audio.frequencies)

        bars = bars_from_spectrum(audio.spectrum, self._idx)
        bars = np.clip(bars * settings.sensitivity, 0.0, 1.0).astype("f4")
        self.bar_tex.write(np.ascontiguousarray(bars).tobytes())

        _, _, w, h = self.ctx.viewport
        palette_lut.use(0)
        self.bar_tex.use(1)
        self.prog["palette"] = 0
        self.prog["bars"] = 1
        self.prog["bg"] = tuple(background)
        self.prog["aspect"] = (w / h) if h else 1.0
        self.prog["volume"] = float(audio.volume)
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        self.bar_tex.release()
        self.vao.release()
        self.prog.release()
