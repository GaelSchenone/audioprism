"""3D spectrum bars: frequency bars in perspective space, orbitable with mouse."""

from __future__ import annotations

import numpy as np
import moderngl

from src.audio.analyzer import AudioData
from src.config.settings import VisualizerSettings
from src.presets.base import Preset
from src.presets.bars import make_log_bins, bars_from_spectrum

_VERT = """
#version 330
in vec3 in_pos;       // (x, z, base_y)
in float in_idx;      // 0..1 bar index for palette lookup
out float v_pal_t;
uniform mat4 mvp;
uniform sampler2D bars;       // width=NBARS, height=1, r = magnitude
uniform float aspect;
uniform float bar_width;
uniform float volume;
void main() {
    float mag = texture(bars, vec2(in_idx, 0.5)).r;
    float h = mag * (0.5 + volume * 0.3);
    float spread = 1.2;
    float x = (in_pos.x - 0.5) * spread * aspect;
    float z = in_pos.z * spread;
    vec3 p = vec3(x, h * 0.5, z);
    v_pal_t = h;
    vec4 clip = mvp * vec4(p, 1.0);
    gl_Position = clip;
    gl_PointSize = 1.0;
}
"""

_GEOM = """
#version 330
layout(triangles) in;
layout(triangle_strip, max_vertices=4) out;
in float v_pal_t[];
out vec2 g_uv;
out float g_pal_t;
uniform float bar_width;
uniform float aspect;
void main() {
    // Emit a quad at each bar position, facing the camera approximately
    // by using screen-space orientation. For simplicity: a fixed-width billboard.
    vec3 pos = gl_in[0].gl_Position.xyz;
    float w = bar_width;
    float h = gl_in[0].gl_Position.y * 2.0;   // height from vertex

    // Simple quad facing the viewer (clip-space expansion)
    vec4 base = gl_in[0].gl_Position;
    // Actually let's just do point rendering for now — billboards are complex
}
"""

_FRAG = """
#version 330
in float v_pal_t;
out vec4 frag;
uniform sampler2D palette;
void main() {
    float t = clamp(v_pal_t, 0.0, 1.0);
    vec3 col = texture(palette, vec2(t, 0.5)).rgb;
    frag = vec4(col, 1.0);
}
"""


class Spectrum3D(Preset):
    name = "spectrum_3d"
    NBARS = 64
    FMIN = 30.0
    FMAX = 16000.0
    params = ("point_size",)

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.spectrum_tex = ctx.texture((self.NBARS, 1), 1, dtype="f4")
        self.spectrum_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.spectrum_tex.repeat_x = False

        # Build bar positions: each bar is a thin quad (2 tris = 6 verts)
        n = self.NBARS
        self._bar_width = 0.6 / n
        verts = []
        for i in range(n):
            x = (i + 0.5) / n
            idx = i / (n - 1)
            z = 0.0
            # Quad: two triangles, 6 vertices
            for dx, dz in [(-self._bar_width, -0.02), (self._bar_width, -0.02),
                           (self._bar_width, 0.02), (-self._bar_width, -0.02),
                           (self._bar_width, 0.02), (-self._bar_width, 0.02)]:
                verts.append((x + dx, z + dz, 0.0, idx))
        verts = np.array(verts, dtype="f4")
        self.n_verts = len(verts)

        self.vbo = ctx.buffer(np.ascontiguousarray(verts).tobytes())
        self.vao = ctx.vertex_array(
            self.prog, [(self.vbo, "3f 1f", "in_pos", "in_idx")]
        )

        self._idx: np.ndarray | None = None
        self._freqs_len = -1
        self._mvp = np.eye(4, dtype="f4")

    def set_mvp(self, mvp: np.ndarray) -> None:
        self._mvp = mvp

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
        self.spectrum_tex.write(np.ascontiguousarray(bars).tobytes())

        _, _, w, h = self.ctx.viewport
        aspect = (w / h) if h else 1.0
        self.ctx.enable(moderngl.DEPTH_TEST)

        palette_lut.use(0)
        self.spectrum_tex.use(1)
        self.prog["palette"] = 0
        self.prog["bars"] = 1
        self.prog["mvp"].write(np.ascontiguousarray(self._mvp, dtype="f4").tobytes())
        self.prog["aspect"] = aspect
        self.prog["bar_width"] = self._bar_width
        self.prog["volume"] = float(audio.volume)
        self.vao.render(mode=moderngl.TRIANGLES, vertices=self.n_verts)

        self.ctx.disable(moderngl.DEPTH_TEST)

    def release(self) -> None:
        self.spectrum_tex.release()
        self.vbo.release()
        self.vao.release()
        self.prog.release()
