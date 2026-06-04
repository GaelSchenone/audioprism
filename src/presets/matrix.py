"""Matrix preset: digital rain reacting to volume (procedural glyph cells)."""

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
in vec2 v_uv; out vec4 frag;
uniform sampler2D palette;
uniform vec3 bg;
uniform vec2 grid;       // columns, rows
uniform float time;
uniform float volume;

float hash11(float p) { p = fract(p * 0.1031); p *= p + 33.33; p *= p + p; return fract(p); }
float hash21(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

void main() {
    vec2 cell = floor(v_uv * grid);
    vec2 local = fract(v_uv * grid);
    float col = cell.x;

    float speed = (0.4 + hash11(col) * 0.8) * (0.5 + volume * 2.0);
    float headNorm = fract(hash11(col) * 7.0 + time * speed * 0.15);
    float headY = 1.0 - headNorm;                       // falls top → bottom
    float cellY = (cell.y + 0.5) / grid.y;

    float d = cellY - headY;                            // tail trails above head
    float tail = 0.32;
    float trail = (d >= 0.0 && d < tail) ? (1.0 - d / tail) : 0.0;
    float head = smoothstep(0.06, 0.0, abs(d));
    float intensity = clamp(trail * 0.7 + head, 0.0, 1.5) * (0.45 + volume);

    // Procedural 5x7 glyph that flickers over time
    vec2 sub = floor(local * vec2(5.0, 7.0));
    float charId = floor(time * 8.0 * (0.3 + hash11(col + 5.0)) + hash21(cell));
    float on = step(0.5, hash21(sub + charId * 1.7 + cell * 3.1));
    float incell = step(0.08, local.x) * step(local.x, 0.92)
                 * step(0.05, local.y) * step(local.y, 0.95);

    float val = clamp(intensity, 0.0, 1.2) * on * incell;
    vec3 col3 = texture(palette, vec2(clamp(val, 0.0, 1.0), 0.5)).rgb;
    frag = vec4(bg + col3 * val, 1.0);
}
"""


class Matrix(Preset):
    name = "matrix"
    COLS = 48
    _DT = 1.0 / 60.0

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
        self.time += self._DT
        _, _, w, h = self.ctx.viewport
        aspect = (w / h) if h else 1.0
        cols = max(8, int(settings.matrix_density))
        rows = max(8.0, round(cols / aspect))

        palette_lut.use(0)
        self.prog["palette"] = 0
        self.prog["bg"] = tuple(background)
        self.prog["grid"] = (float(cols), float(rows))
        self.prog["time"] = float(self.time)
        self.prog["volume"] = float(audio.volume)
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        self.vao.release()
        self.prog.release()
