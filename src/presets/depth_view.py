"""depth preset: live monocular depth map, palette-colored.

A 2D view of the webcam depth (near = high end of the palette, far = low end),
so the depth layer is visible on its own before it drives the 3D point cloud.
"""

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
in vec2 v_uv; out vec4 frag;
uniform sampler2D depth;     // single channel, 0=far 1=near
uniform sampler2D palette;
uniform vec3 bg;
uniform float volume;
uniform float time;
uniform float waiting;       // 1.0 = no depth data yet

void main() {
    vec2 uv = vec2(1.0 - v_uv.x, 1.0 - v_uv.y);
    if (waiting > 0.5) {
        // Pulsing "loading" indicator
        float pulse = 0.5 + 0.5 * sin(time * 2.0);
        float r = length(v_uv - 0.5) * 1.8;
        float glow = exp(-r * 3.0) * pulse * 0.3;
        frag = vec4(bg + glow, 1.0);
        return;
    }
    float d = texture(depth, uv).r;
    vec3 col = texture(palette, vec2(d, 0.5)).rgb;
    frag = vec4(col * (0.75 + 0.25 * volume), 1.0);
}
"""


_DT = 1.0 / 60.0


class Depth(Preset):
    name = "depth"
    needs_depth = True

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.vao = fullscreen_vao(ctx, self.prog)
        self._depth: np.ndarray | None = None
        self._tex: moderngl.Texture | None = None
        self._shape: tuple[int, int] | None = None
        self._time = 0.0

    def set_depth(self, depth: np.ndarray | None) -> None:
        self._depth = depth

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        self._time += _DT
        waiting = self._depth is None

        palette_lut.use(0)
        self.prog["palette"] = 0
        self.prog["bg"] = tuple(background)
        self.prog["volume"] = float(audio.volume)
        self.prog["time"] = float(self._time)
        self.prog["waiting"] = 1.0 if waiting else 0.0

        if waiting:
            self.vao.render(moderngl.TRIANGLES)
            return

        h, w = self._depth.shape[:2]
        if self._shape != (h, w) or self._tex is None:
            if self._tex is not None:
                self._tex.release()
            self._tex = self.ctx.texture((w, h), 1, dtype="f4")
            self._tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._tex.repeat_x = self._tex.repeat_y = False
            self._shape = (h, w)
        self._tex.write(np.ascontiguousarray(self._depth, dtype="f4").tobytes())

        self._tex.use(1)
        self.prog["depth"] = 1
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        if self._tex is not None:
            self._tex.release()
        self.vao.release()
        self.prog.release()
