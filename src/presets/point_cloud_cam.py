"""point_cloud_cam: the live webcam as a 3D point cloud with real depth.

Each grid point samples the video frame (true color) and the monocular depth map
(MiDaS) for its Z, so the scene pops out in 3D. Bass amplifies the depth and
beats push the whole cloud toward the camera. Orbit with the mouse, zoom with
scroll.
"""

from __future__ import annotations

import numpy as np
import moderngl

from src.audio.analyzer import AudioData
from src.config.settings import VisualizerSettings
from src.presets.base import Preset

_VERT = """
#version 330
in vec2 in_uv;
out vec3 v_col;
uniform mat4 mvp;
uniform sampler2D frame;
uniform sampler2D depth;
uniform float z_scale;
uniform float bass;
uniform float push;
uniform float point_scale;
uniform float plane_w;
void main() {
    vec2 uv = in_uv;
    v_col = texture(frame, uv).rgb;
    float d = texture(depth, uv).r;                 // 0 far .. 1 near
    float x = (uv.x - 0.5) * 2.0 * plane_w;
    float y = (0.5 - uv.y) * 2.0;
    float z = (d - 0.45) * z_scale * (1.0 + bass * 0.8) + push;
    vec4 clip = mvp * vec4(x, y, z, 1.0);
    gl_Position = clip;
    gl_PointSize = clamp(point_scale / max(clip.w, 0.1), 1.0, 14.0);
}
"""

_FRAG = """
#version 330
in vec3 v_col; out vec4 frag;
void main() {
    if (length(gl_PointCoord - vec2(0.5)) > 0.5) discard;
    frag = vec4(v_col, 1.0);
}
"""

_DT = 1.0 / 60.0
_GRID_W = 200
_GRID_H = 150


class PointCloudCam(Preset):
    name = "point_cloud_cam"
    needs_video = True
    needs_depth = True
    params = ("point_size",)

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        gx, gy = np.meshgrid(
            (np.arange(_GRID_W) + 0.5) / _GRID_W,
            (np.arange(_GRID_H) + 0.5) / _GRID_H,
        )
        uv = np.column_stack([gx.ravel(), gy.ravel()]).astype("f4")
        self.n = len(uv)
        self.vbo = ctx.buffer(np.ascontiguousarray(uv).tobytes())
        self.vao = ctx.vertex_array(self.prog, [(self.vbo, "2f", "in_uv")])

        self._frame: np.ndarray | None = None
        self._depth: np.ndarray | None = None
        self._frame_tex: moderngl.Texture | None = None
        self._depth_tex: moderngl.Texture | None = None
        self._frame_shape: tuple[int, int] | None = None
        self._depth_shape: tuple[int, int] | None = None
        self._mvp = np.eye(4, dtype="f4")
        self.flash = 0.0

    def set_frame(self, frame: np.ndarray | None) -> None:
        self._frame = frame

    def set_depth(self, depth: np.ndarray | None) -> None:
        self._depth = depth

    def set_mvp(self, mvp: np.ndarray) -> None:
        self._mvp = mvp

    def _upload(self) -> bool:
        if self._frame is None or self._depth is None:
            return False
        fh, fw = self._frame.shape[:2]
        if self._frame_shape != (fh, fw):
            if self._frame_tex is not None:
                self._frame_tex.release()
            self._frame_tex = self.ctx.texture((fw, fh), 3, dtype="f1")
            self._frame_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._frame_shape = (fh, fw)
        self._frame_tex.write(np.ascontiguousarray(self._frame).tobytes())

        dh, dw = self._depth.shape[:2]
        if self._depth_shape != (dh, dw):
            if self._depth_tex is not None:
                self._depth_tex.release()
            self._depth_tex = self.ctx.texture((dw, dh), 1, dtype="f4")
            self._depth_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._depth_shape = (dh, dw)
        self._depth_tex.write(np.ascontiguousarray(self._depth, dtype="f4").tobytes())
        return True

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        self.flash = max(0.0, self.flash * 0.88)
        if audio.beat:
            self.flash = 1.0
        if not self._upload():
            return

        fh, fw = self._frame_shape
        _, _, w, h = self.ctx.viewport
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)

        self._frame_tex.use(0)
        self._depth_tex.use(1)
        self.prog["frame"] = 0
        self.prog["depth"] = 1
        self.prog["mvp"].write(np.ascontiguousarray(self._mvp, dtype="f4").tobytes())
        self.prog["z_scale"] = 1.3
        self.prog["bass"] = float(audio.bands.get("bass", 0.0))
        self.prog["push"] = float(self.flash) * 0.4
        self.prog["plane_w"] = fw / fh
        self.prog["point_scale"] = max(2.0, h * 0.02) * settings.point_size
        self.vao.render(mode=moderngl.POINTS, vertices=self.n)

        self.ctx.disable(moderngl.DEPTH_TEST)

    def release(self) -> None:
        if self._frame_tex is not None:
            self._frame_tex.release()
        if self._depth_tex is not None:
            self._depth_tex.release()
        self.vbo.release()
        self.vao.release()
        self.prog.release()
