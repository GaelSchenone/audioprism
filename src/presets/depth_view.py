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
uniform float volume;
void main() {
    vec2 uv = vec2(1.0 - v_uv.x, 1.0 - v_uv.y);   // upright + selfie mirror
    float d = texture(depth, uv).r;
    vec3 col = texture(palette, vec2(d, 0.5)).rgb;
    frag = vec4(col * (0.75 + 0.25 * volume), 1.0);
}
"""


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

    def set_depth(self, depth: np.ndarray | None) -> None:
        self._depth = depth

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        if self._depth is None:
            return
        h, w = self._depth.shape[:2]
        if self._shape != (h, w):
            if self._tex is not None:
                self._tex.release()
            self._tex = self.ctx.texture((w, h), 1, dtype="f4")
            self._tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._tex.repeat_x = self._tex.repeat_y = False
            self._shape = (h, w)
        self._tex.write(np.ascontiguousarray(self._depth, dtype="f4").tobytes())

        palette_lut.use(0)
        self._tex.use(1)
        self.prog["palette"] = 0
        self.prog["depth"] = 1
        self.prog["volume"] = float(audio.volume)
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        if self._tex is not None:
            self._tex.release()
        self.vao.release()
        self.prog.release()
