"""GLViewport: a QOpenGLWidget that renders the engine and blits it to screen.

Reused for both the editor preview and the fullscreen window. Each instance owns
its own moderngl context + VisualizerEngine, pulling shared state (audio, palette,
preset, settings) from the controller every frame.
"""

from __future__ import annotations

import moderngl
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from src.engine import VisualizerEngine
from src.presets.base import fullscreen_vao

_BLIT_VERT = """
#version 330
in vec2 in_pos;
out vec2 v_uv;
void main() {
    v_uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

_BLIT_FRAG = """
#version 330
in vec2 v_uv;
out vec4 frag;
uniform sampler2D tex;
void main() { frag = texture(tex, v_uv); }
"""


class GLViewport(QOpenGLWidget):
    def __init__(self, controller, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.ctx: moderngl.Context | None = None
        self.engine: VisualizerEngine | None = None
        self._seen_palette = -1

    def _device_size(self) -> tuple[int, int]:
        dpr = self.devicePixelRatio()
        return max(2, int(self.width() * dpr)), max(2, int(self.height() * dpr))

    def initializeGL(self) -> None:
        self.ctx = moderngl.create_context()
        self.engine = VisualizerEngine(
            self.ctx,
            self._device_size(),
            self.controller.palette,
            self.controller.settings,
        )
        self.engine.set_preset(self.controller.settings.preset)
        self._seen_palette = self.controller.palette_version
        self.blit_prog = self.ctx.program(vertex_shader=_BLIT_VERT, fragment_shader=_BLIT_FRAG)
        self.blit_vao = fullscreen_vao(self.ctx, self.blit_prog)

    def resizeGL(self, w: int, h: int) -> None:
        if self.engine:
            self.engine.resize(max(2, w), max(2, h))

    def paintGL(self) -> None:
        if self.engine is None:
            return
        # Sync config pulled from the controller
        if self._seen_palette != self.controller.palette_version:
            self.engine.set_palette(self.controller.palette)
            self._seen_palette = self.controller.palette_version
        self.engine.set_preset(self.controller.settings.preset)
        self.engine.settings = self.controller.settings

        # Render the visualization into the engine's offscreen FBO
        self.engine.render(self.controller.latest_audio)

        # Blit the result to the widget's framebuffer
        screen = self.ctx.detect_framebuffer(self.defaultFramebufferObject())
        screen.use()
        fbw, fbh = self._device_size()
        self.ctx.viewport = (0, 0, fbw, fbh)
        self.engine.output_texture.use(0)
        self.blit_prog["tex"] = 0
        self.blit_vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        if self.engine:
            self.makeCurrent()
            self.engine.release()
            self.blit_vao.release()
            self.blit_prog.release()
            self.doneCurrent()
            self.engine = None
