"""Particles preset: audio-reactive GPU point cloud with a deterministic CPU sim.

The simulation runs on the CPU with a fixed-seed RNG so every engine instance
(editor preview and fullscreen window) produces an identical cloud from the same
audio stream. Bass drives emission and outward speed; beats trigger bursts.
Particles are drawn as additive soft points, colored from the palette by age.
"""

from __future__ import annotations

import numpy as np
import moderngl

from src.audio.analyzer import AudioData
from src.config.settings import VisualizerSettings
from src.presets.base import Preset

_VERT = """
#version 330
in vec2 in_pos;
in float in_life;
out float v_life;
uniform float aspect;
uniform float point_scale;
void main() {
    vec2 p = in_pos;
    if (aspect > 1.0) p.x /= aspect; else p.y *= aspect;   // keep bursts circular
    v_life = in_life;
    gl_Position = vec4(p, 0.0, 1.0);
    gl_PointSize = point_scale * (0.4 + clamp(in_life, 0.0, 1.0));
}
"""

_FRAG = """
#version 330
in float v_life;
out vec4 frag;
uniform sampler2D palette;
void main() {
    float r = length(gl_PointCoord - vec2(0.5));
    if (r > 0.5) discard;
    float a = smoothstep(0.5, 0.0, r);
    vec3 col = texture(palette, vec2(clamp(1.0 - v_life, 0.0, 1.0), 0.5)).rgb;
    frag = vec4(col * a, a);
}
"""

_DT = 1.0 / 60.0
_DRAG = 0.985
_LIFE_DECAY = 0.8
_SWIRL = 0.6


class Particles(Preset):
    name = "particles"
    params = ("particle_count", "particle_turbulence")

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.max_n = 60000
        self.n = 20000                                       # active (from settings)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.vbo = ctx.buffer(reserve=self.max_n * 3 * 4)    # pos(2f) + life(1f)
        self.vao = ctx.vertex_array(
            self.prog, [(self.vbo, "2f 1f", "in_pos", "in_life")]
        )

        self.rng = np.random.default_rng(1234)               # deterministic
        self.pos = np.zeros((self.max_n, 2), dtype="f4")
        self.vel = np.zeros((self.max_n, 2), dtype="f4")
        self.life = np.zeros(self.max_n, dtype="f4")         # all dead initially
        self._interleaved = np.zeros((self.max_n, 3), dtype="f4")
        self._sim_time = 0.0
        self._turbulence = 0.3

    def _emit(self, count: int, bass: float, beat: bool) -> None:
        if count <= 0:
            return
        dead = np.where(self.life[:self.n] <= 0.0)[0]
        if len(dead) == 0:
            return
        k = min(count, len(dead))
        idx = dead[:k]
        angle = self.rng.uniform(0.0, 2.0 * np.pi, k).astype("f4")
        speed = (0.35 + bass * 1.8 + (0.9 if beat else 0.0)) * self.rng.uniform(0.5, 1.0, k)
        self.pos[idx] = self.rng.normal(0.0, 0.02, (k, 2)).astype("f4")
        self.vel[idx, 0] = np.cos(angle) * speed
        self.vel[idx, 1] = np.sin(angle) * speed
        self.life[idx] = 1.0

    def _step(self, audio: AudioData) -> None:
        bass = float(audio.bands.get("bass", 0.0))
        beat = bool(audio.beat)
        turbulence = self._turbulence

        n_emit = int(self.n * 0.008 + bass * self.n * 0.03)
        if beat:
            n_emit += int(self.n * 0.12)
        self._emit(n_emit, bass, beat)

        n = self.n
        life, vel, pos = self.life[:n], self.vel[:n], self.pos[:n]
        alive = life > 0.0
        # Swirl: rotate velocities slightly for visual motion
        ang = _SWIRL * _DT
        cos_a, sin_a = np.cos(ang), np.sin(ang)
        vx, vy = vel[alive, 0].copy(), vel[alive, 1].copy()
        vel[alive, 0] = vx * cos_a - vy * sin_a
        vel[alive, 1] = vx * sin_a + vy * cos_a

        # Turbulence: noise-like offset based on position + time
        if turbulence > 0.01:
            t = self._sim_time
            idx_alive = np.where(alive)[0]
            if len(idx_alive) > 0:
                px = pos[alive, 0]
                py = pos[alive, 1]
                noise_x = np.sin(px * 5.0 + t * 2.0) * np.cos(py * 3.0 + t * 1.3)
                noise_y = np.sin(py * 5.0 + t * 2.3) * np.cos(px * 4.0 + t * 1.7)
                vel[alive, 0] += noise_x * turbulence * 0.02
                vel[alive, 1] += noise_y * turbulence * 0.02

        pos[alive] += vel[alive] * _DT
        vel[alive] *= _DRAG
        life[alive] -= _DT * _LIFE_DECAY
        self._sim_time += _DT

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        self.n = int(np.clip(settings.particle_count, 500, self.max_n))
        self._turbulence = float(settings.particle_turbulence)
        self._step(audio)

        n = self.n
        self._interleaved[:n, :2] = self.pos[:n]
        self._interleaved[:n, 2] = np.clip(self.life[:n], 0.0, 1.0)
        self.vbo.write(np.ascontiguousarray(self._interleaved[:n]).tobytes())

        _, _, w, h = self.ctx.viewport
        self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)   # additive

        palette_lut.use(0)
        self.prog["palette"] = 0
        self.prog["aspect"] = (w / h) if h else 1.0
        self.prog["point_scale"] = max(2.0, h * 0.010)
        self.vao.render(mode=moderngl.POINTS, vertices=n)

        # Restore default blending so the bloom passes composite correctly
        self.ctx.disable(moderngl.BLEND)

    def release(self) -> None:
        self.vbo.release()
        self.vao.release()
        self.prog.release()
