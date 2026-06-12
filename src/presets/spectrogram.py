"""Spectrogram preset: waterfall FFT — time scrolls upward, frequency rightward."""

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
in vec2 v_uv; out vec4 frag;
uniform sampler2D hist;      // NBINS × H_HISTORY, r = magnitude
uniform sampler2D palette;
uniform vec3 bg;
uniform float write_row;
uniform float total_rows;
void main() {
    // Wrap time-axis so the waterfall cycles seamlessly
    float t = v_uv.y * total_rows;
    float row = mod(write_row - t, total_rows);
    float x = v_uv.x;
    float mag = texture(hist, vec2(x, (row + 0.5) / total_rows)).r;
    vec3 col = texture(palette, vec2(mag, 0.5)).rgb;
    frag = vec4(bg + col * mag, 1.0);
}
"""

_H_HISTORY = 200
_NBINS = 256


class Spectrogram(Preset):
    name = "spectrogram"
    FMIN = 30.0
    FMAX = 16000.0

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.vao = fullscreen_vao(ctx, self.prog)
        self.hist_tex = ctx.texture((_NBINS, _H_HISTORY), 1, dtype="f4")
        self.hist_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.hist_tex.repeat_x = False
        self.hist_tex.repeat_y = True               # wrap for seamless scroll
        self._write_row = 0
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
            self._idx = make_log_bins(audio.frequencies, _NBINS, self.FMIN, self.FMAX)
            self._freqs_len = len(audio.frequencies)

        bars = bars_from_spectrum(audio.spectrum, self._idx)
        bars = np.clip(bars * settings.sensitivity, 0.0, 1.0).astype("f4")
        # Write one row into the circular buffer at the current write position
        self.hist_tex.write(
            np.ascontiguousarray(bars).tobytes(),
            viewport=(0, self._write_row, _NBINS, 1),
        )
        self._write_row = (self._write_row + 1) % _H_HISTORY

        palette_lut.use(0)
        self.hist_tex.use(1)
        self.prog["palette"] = 0
        self.prog["hist"] = 1
        self.prog["bg"] = tuple(background)
        self.prog["write_row"] = float(self._write_row - 1) % _H_HISTORY
        self.prog["total_rows"] = float(_H_HISTORY)
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        self.hist_tex.release()
        self.vao.release()
        self.prog.release()
