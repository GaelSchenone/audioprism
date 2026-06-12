"""Plasma preset: audio-reactive noise field — four summed sine waves."""

from __future__ import annotations

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
#define PI 3.14159265
in vec2 v_uv; out vec4 frag;
uniform sampler2D palette;
uniform vec3 bg;
uniform float time;
uniform float sub_bass;
uniform float bass;
uniform float mid;
uniform float high;
uniform float beat;
uniform float speed;

void main() {
    vec2 p = v_uv * 2.0 - 1.0;
    float t = time * speed;

    // Four waves, each tied to a frequency band
    float w1 = sin(p.x * 4.0 + p.y * 3.0 + t * 0.7 + sub_bass * 2.0);
    float w2 = sin(p.x * 5.0 - p.y * 6.0 + t * 1.1 + bass * 3.0);
    float w3 = sin((p.x * 2.0 + p.y * 3.0) * 3.0 + t * 1.5 + mid * 4.0);
    float w4 = sin((p.y - p.x) * 8.0 + t * 2.3 + high * 5.0);

    // Beat kick: phase distortion
    float kick = beat * 0.5 * sin(t * 20.0 * beat);
    float v = (w1 + w2 + w3 + w4) * 0.25 + kick;

    // Map to palette via intensity
    float intensity = clamp(v * 0.5 + 0.5, 0.0, 1.0);
    vec3 col = texture(palette, vec2(intensity, 0.5)).rgb;
    frag = vec4(bg + col * (0.5 + 0.5 * intensity), 1.0);
}
"""

_DT = 1.0 / 60.0


class Plasma(Preset):
    name = "plasma"
    params = ("plasma_speed",)

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.vao = fullscreen_vao(ctx, self.prog)
        self.time = 0.0

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        self.time += _DT

        palette_lut.use(0)
        self.prog["palette"] = 0
        self.prog["bg"] = tuple(background)
        self.prog["time"] = float(self.time)
        self.prog["sub_bass"] = float(audio.bands.get("sub_bass", 0.0))
        self.prog["bass"] = float(audio.bands.get("bass", 0.0))
        self.prog["mid"] = float(audio.bands.get("mid", 0.0))
        self.prog["high"] = float(audio.bands.get("high", 0.0))
        self.prog["beat"] = 1.0 if audio.beat else 0.0
        self.prog["speed"] = float(settings.plasma_speed)
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        self.vao.release()
        self.prog.release()
