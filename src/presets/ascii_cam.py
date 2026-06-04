"""ascii_cam preset: live webcam/video rendered as audio-reactive ASCII art.

Each grid cell samples the video frame, maps brightness to a glyph from the
AsciiAtlas, and tints it with the palette. Audio modulates it: volume brightens,
bass injects horizontal glitch on scattered rows, and beats flash. The grid
density (definition) is driven by settings.ascii_grid.
"""

from __future__ import annotations

import numpy as np
import moderngl

from src.audio.analyzer import AudioData
from src.ascii_atlas import AsciiAtlas
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
uniform sampler2D frame;      // RGB video frame
uniform sampler2D atlas;      // glyph strip
uniform sampler2D palette;
uniform vec3 bg;
uniform vec2 grid;            // cols, rows
uniform float natlas;
uniform float volume;
uniform float bass;
uniform float flash;          // decaying beat flash 0..1
uniform float time;

float hash11(float p) { p = fract(p * 0.1031); p *= p + 33.33; p *= p + p; return fract(p); }

void main() {
    vec2 cell = floor(v_uv * grid);
    vec2 local = fract(v_uv * grid);
    vec2 cc = (cell + 0.5) / grid;

    // Bass glitch: shift scattered rows horizontally
    float rk = hash11(cell.y + floor(time * 6.0));
    float glitch = (rk < bass * 0.6) ? (rk - 0.5) * bass * 0.25 : 0.0;

    // Frame is top-origin; flip v. Mirror x for a selfie feel.
    vec2 fuv = vec2(1.0 - (cc.x + glitch), 1.0 - cc.y);
    vec3 src = texture(frame, fuv).rgb;

    float bright = dot(src, vec3(0.2126, 0.7152, 0.0722));
    bright = clamp(bright * (0.6 + volume) + flash * 0.5, 0.0, 1.0);

    float gi = floor(bright * (natlas - 1.0) + 0.5);
    float gx = (gi + local.x) / natlas;
    float ink = texture(atlas, vec2(gx, local.y)).r;

    vec3 col = texture(palette, vec2(bright, 0.5)).rgb;
    frag = vec4(bg + col * ink, 1.0);
}
"""

_DT = 1.0 / 60.0


class AsciiCam(Preset):
    name = "ascii_cam"
    needs_video = True

    def __init__(self, ctx: moderngl.Context) -> None:
        super().__init__(ctx)
        self.prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.vao = fullscreen_vao(ctx, self.prog)
        self.atlas = AsciiAtlas()
        self.atlas_tex = self.atlas.texture(ctx)
        self._glyph_aspect = self.atlas.cell_w / self.atlas.cell_h

        self._frame: np.ndarray | None = None
        self._frame_tex: moderngl.Texture | None = None
        self._frame_shape: tuple[int, int] | None = None
        self.time = 0.0
        self.flash = 0.0

    def set_frame(self, frame: np.ndarray | None) -> None:
        self._frame = frame

    def _upload_frame(self) -> bool:
        if self._frame is None:
            return False
        h, w = self._frame.shape[:2]
        if self._frame_shape != (h, w):
            if self._frame_tex is not None:
                self._frame_tex.release()
            self._frame_tex = self.ctx.texture((w, h), 3, dtype="f1")
            self._frame_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._frame_tex.repeat_x = self._frame_tex.repeat_y = False
            self._frame_shape = (h, w)
        self._frame_tex.write(np.ascontiguousarray(self._frame).tobytes())
        return True

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        self.time += _DT
        self.flash = max(0.0, self.flash * 0.85)
        if audio.beat:
            self.flash = 1.0

        if not self._upload_frame():
            return                                      # no frame yet → bg only

        fh, fw = self._frame_shape
        frame_aspect = fw / fh
        _, _, vw, vh = self.ctx.viewport
        view_aspect = (vw / vh) if vh else 1.0

        cols = max(8, int(settings.ascii_grid))
        # rows from the on-screen cell shape so glyphs aren't stretched
        rows = max(6, round(cols / view_aspect * self._glyph_aspect))

        palette_lut.use(0)
        self._frame_tex.use(1)
        self.atlas_tex.use(2)
        self.prog["palette"] = 0
        self.prog["frame"] = 1
        self.prog["atlas"] = 2
        self.prog["bg"] = tuple(background)
        self.prog["grid"] = (float(cols), float(rows))
        self.prog["natlas"] = float(self.atlas.n)
        self.prog["volume"] = float(audio.volume)
        self.prog["bass"] = float(audio.bands.get("bass", 0.0))
        self.prog["flash"] = float(self.flash)
        self.prog["time"] = float(self.time)
        self.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        if self._frame_tex is not None:
            self._frame_tex.release()
        self.atlas_tex.release()
        self.vao.release()
        self.prog.release()
