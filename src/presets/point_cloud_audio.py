"""point_cloud_audio: a 3D nebula of points driven by the FFT spectrum.

Points sit on a fuzzy sphere (Fibonacci distribution); each samples a frequency
bin by its height, so loud bands push points outward into spikes. The cloud
rotates over time and pulses with volume. Orbit with the mouse, zoom with scroll.
"""

from __future__ import annotations

import numpy as np
import moderngl

from src.audio.analyzer import AudioData
from src.config.settings import VisualizerSettings
from src.presets.base import Preset
from src.presets.bars import make_log_bins, bars_from_spectrum

_VERT = """
#version 330
in vec3 in_dir;
in float in_t;
in float in_base_r;
out float v_mag;
uniform mat4 mvp;
uniform sampler2D spectrum;     // NBINS wide, r = magnitude
uniform float time;
uniform float volume;
uniform float point_scale;
void main() {
    float a = time * 0.2;
    mat2 rot = mat2(cos(a), -sin(a), sin(a), cos(a));
    vec3 d = in_dir;
    d.xz = rot * d.xz;
    float mag = texture(spectrum, vec2(in_t, 0.5)).r;
    v_mag = mag;
    float r = in_base_r * (1.0 + mag * 1.6) * (0.6 + volume * 0.7);
    vec4 clip = mvp * vec4(d * r, 1.0);
    gl_Position = clip;
    gl_PointSize = clamp(point_scale * (0.4 + mag) / max(clip.w, 0.1), 1.0, 40.0);
}
"""

_FRAG = """
#version 330
in float v_mag;
out vec4 frag;
uniform sampler2D palette;
void main() {
    float r = length(gl_PointCoord - vec2(0.5));
    if (r > 0.5) discard;
    float a = smoothstep(0.5, 0.0, r);
    vec3 col = texture(palette, vec2(clamp(v_mag * 1.5 + 0.1, 0.0, 1.0), 0.5)).rgb;
    frag = vec4(col * a, a);
}
"""

_DT = 1.0 / 60.0
_NBINS = 256


def _fibonacci_sphere(n: int) -> np.ndarray:
    i = np.arange(n, dtype=np.float64)
    phi = np.pi * (3.0 - np.sqrt(5.0))           # golden angle
    y = 1.0 - 2.0 * (i + 0.5) / n
    radius = np.sqrt(np.maximum(0.0, 1.0 - y * y))
    theta = phi * i
    return np.stack([np.cos(theta) * radius, y, np.sin(theta) * radius], axis=1)


class PointCloudAudio(Preset):
    name = "point_cloud_audio"

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.n = 30000
        rng = np.random.default_rng(7)               # deterministic across engines
        dirs = _fibonacci_sphere(self.n).astype("f4")
        t = ((dirs[:, 1] + 1.0) * 0.5).astype("f4")  # frequency by height
        base_r = (0.8 + rng.random(self.n) * 0.4).astype("f4")
        data = np.column_stack([dirs, t, base_r]).astype("f4")

        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.vbo = ctx.buffer(np.ascontiguousarray(data).tobytes())
        self.vao = ctx.vertex_array(
            self.prog, [(self.vbo, "3f 1f 1f", "in_dir", "in_t", "in_base_r")]
        )
        self.spectrum_tex = ctx.texture((_NBINS, 1), 1, dtype="f4")
        self.spectrum_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.spectrum_tex.repeat_x = False
        self._idx: np.ndarray | None = None
        self._freqs_len = -1
        self.time = 0.0
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
        self.time += _DT
        if self._freqs_len != len(audio.frequencies):
            self._idx = make_log_bins(audio.frequencies, _NBINS)
            self._freqs_len = len(audio.frequencies)
        bars = bars_from_spectrum(audio.spectrum, self._idx)
        bars = np.clip(bars * settings.sensitivity, 0.0, 1.0).astype("f4")
        self.spectrum_tex.write(np.ascontiguousarray(bars).tobytes())

        _, _, w, h = self.ctx.viewport
        self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)

        palette_lut.use(0)
        self.spectrum_tex.use(1)
        self.prog["palette"] = 0
        self.prog["spectrum"] = 1
        self.prog["mvp"].write(np.ascontiguousarray(self._mvp, dtype="f4").tobytes())
        self.prog["time"] = float(self.time)
        self.prog["volume"] = float(audio.volume)
        self.prog["point_scale"] = max(2.0, h * 0.05)
        self.vao.render(mode=moderngl.POINTS, vertices=self.n)

        self.ctx.disable(moderngl.BLEND)

    def release(self) -> None:
        self.spectrum_tex.release()
        self.vbo.release()
        self.vao.release()
        self.prog.release()
