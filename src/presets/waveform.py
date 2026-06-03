"""Waveform preset: oscilloscope line traced from the raw audio, palette-colored."""

from __future__ import annotations

import numpy as np
import moderngl

from src.audio.analyzer import AudioData
from src.config.settings import VisualizerSettings
from src.presets.base import Preset, fullscreen_vao

_VERT = """
#version 330
in vec2 in_pos;
out vec2 v_uv;
void main() { v_uv = in_pos * 0.5 + 0.5; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

_FRAG = """
#version 330
in vec2 v_uv;
out vec4 frag;
uniform sampler2D wave;       // width=WIDTH, r = sample in [-1, 1]
uniform sampler2D palette;
uniform vec3 bg;
uniform float amp;
void main() {
    float x = v_uv.x;
    float w = texture(wave, vec2(x, 0.5)).r;
    float cy = 0.5 + clamp(w, -1.0, 1.0) * amp;
    float d = abs(v_uv.y - cy);
    float core = smoothstep(0.012, 0.0, d);       // crisp line
    float glow = smoothstep(0.06, 0.0, d) * 0.25; // soft edge; bloom extends it
    vec3 col = texture(palette, vec2(x, 0.5)).rgb;
    frag = vec4(bg + col * (core + glow), 1.0);
}
"""


class Waveform(Preset):
    name = "waveform"
    WIDTH = 2048

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.vao = fullscreen_vao(ctx, self.prog)
        self.wave_tex = ctx.texture((self.WIDTH, 1), 1, dtype="f4")
        self.wave_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.wave_tex.repeat_x = False

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        w = audio.waveform
        if len(w) != self.WIDTH:
            xp = np.linspace(0.0, 1.0, len(w))
            w = np.interp(np.linspace(0.0, 1.0, self.WIDTH), xp, w)
        data = np.ascontiguousarray(w * settings.sensitivity, dtype="f4")
        self.wave_tex.write(data.tobytes())

        palette_lut.use(0)
        self.wave_tex.use(1)
        self.prog["palette"] = 0
        self.prog["wave"] = 1
        self.prog["bg"] = tuple(background)
        self.prog["amp"] = 0.42
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        self.wave_tex.release()
        self.vao.release()
        self.prog.release()
