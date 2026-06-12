"""Tunnel preset: perspective ring tunnel with audio-reactive speed and thickness."""

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
uniform float volume;
uniform float bass;
uniform float mid;
uniform float beat;
uniform float density;

void main() {
    // Center UV and apply aspect correction
    vec2 p = v_uv - 0.5;
    float aspect = 1.0;
    // (aspect is applied via the viewport, but we keep circle by remembering p.x *= aspect
    // Actually we handle it in the render() method — here p is already square-ish)

    // Polar coordinates with tunnel perspective
    float r = length(p) * 0.8;
    float theta = atan(p.y, p.x);

    // Avoid division by zero at center
    float r_inv = 1.0 / max(r, 0.001);

    // Speed driven by volume
    float speed = 0.3 + volume * 0.8;
    float t = time * speed;

    // Ring pattern: radial distance from tunnel wall
    float wall = r_inv;
    float rings = fract(wall * density * 0.5 - t);

    // Bass modulates ring thickness
    float thick = 0.15 + bass * 0.3;
    float ring = smoothstep(thick, 0.0, abs(rings - 0.5) * 2.0);

    // Mid modulates angular color variation
    float hue_shift = theta / PI * 0.5 + 0.5 + mid * 0.3;
    float col_val = fract(hue_shift + rings);
    vec3 col = texture(palette, vec2(col_val, 0.5)).rgb;

    // Distance fog
    float fog = 1.0 - exp(-wall * 1.5);
    float brightness = ring * (0.5 + volume * 0.5) * fog;

    // Beat flash
    float flash = beat * 0.4 * exp(-wall * 2.0);

    vec3 out_col = bg + col * brightness + vec3(1.0) * flash;
    frag = vec4(out_col, 1.0);
}
"""

_DT = 1.0 / 60.0


class Tunnel(Preset):
    name = "tunnel"
    params = ("ring_density",)

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
        self.prog["volume"] = float(audio.volume)
        self.prog["bass"] = float(audio.bands.get("bass", 0.0))
        self.prog["mid"] = float(audio.bands.get("mid", 0.0))
        self.prog["beat"] = 1.0 if audio.beat else 0.0
        self.prog["density"] = float(max(4, settings.ring_density))
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        self.vao.release()
        self.prog.release()
