"""Kaleidoscope preset: radial spectrum mirrored into N angular segments."""

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
uniform float segments;
uniform float rotation;

void main() {
    vec2 p = v_uv - 0.5;
    if (aspect > 1.0) p.x *= aspect; else p.y /= aspect;
    float r = length(p) * 2.0;

    // Angle folded into segments with mirror
    float ang = atan(p.y, p.x) + rotation;
    float seg_angle = 2.0 * PI / segments;
    float folded = mod(ang, seg_angle);
    // Mirror within each segment
    float half_seg = seg_angle * 0.5;
    float mirrored = half_seg - abs(folded - half_seg);
    float a01 = mirrored / half_seg;                 // 0–1 within segment

    float mag = texture(bars, vec2(a01, 0.5)).r;

    float inner = 0.15 + volume * 0.05;
    float outer = inner + mag * 0.50;
    float band = smoothstep(inner - 0.004, inner + 0.004, r)
               * (1.0 - smoothstep(outer - 0.010, outer + 0.010, r));
    float ring = smoothstep(0.005, 0.0, abs(r - inner));

    vec3 col = texture(palette, vec2(mag, 0.5)).rgb;
    frag = vec4(bg + col * band + col * ring * 0.6, 1.0);
}
"""


class Kaleidoscope(Preset):
    name = "kaleidoscope"
    NBARS = 180
    FMIN = 30.0
    FMAX = 16000.0
    params = ("kaleidoscope_segments", "kaleidoscope_rotation")

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.vao = fullscreen_vao(ctx, self.prog)
        self.bar_tex = ctx.texture((self.NBARS, 1), 1, dtype="f4")
        self.bar_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.bar_tex.repeat_x = False
        self._idx: np.ndarray | None = None
        self._freqs_len = -1
        self._time = 0.0

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        self._time += 1.0 / 60.0
        if self._freqs_len != len(audio.frequencies):
            self._idx = make_log_bins(audio.frequencies, self.NBARS, self.FMIN, self.FMAX)
            self._freqs_len = len(audio.frequencies)

        bars = bars_from_spectrum(audio.spectrum, self._idx)
        bars = np.clip(bars * settings.sensitivity, 0.0, 1.0).astype("f4")
        self.bar_tex.write(np.ascontiguousarray(bars).tobytes())

        _, _, w, h = self.ctx.viewport
        rot_offset = self._time * settings.kaleidoscope_rotation

        palette_lut.use(0)
        self.bar_tex.use(1)
        self.prog["palette"] = 0
        self.prog["bars"] = 1
        self.prog["bg"] = tuple(background)
        self.prog["aspect"] = (w / h) if h else 1.0
        self.prog["volume"] = float(audio.volume)
        self.prog["segments"] = float(max(2, settings.kaleidoscope_segments))
        self.prog["rotation"] = float(rot_offset)
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        self.bar_tex.release()
        self.vao.release()
        self.prog.release()
