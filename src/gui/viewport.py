"""GLViewport: a QOpenGLWidget that renders the engine and blits it to screen.

Reused for both the editor preview and the fullscreen window. Each instance owns
its own moderngl context + VisualizerEngine, pulling shared state (audio, palette,
preset, settings) from the controller every frame.
"""

from __future__ import annotations

import datetime
import os
import tempfile
import traceback

import numpy as np
import moderngl
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from src.engine import VisualizerEngine
from src.presets.base import fullscreen_vao

_CRASH_LOG = os.path.join(tempfile.gettempdir(), "audioprism_crash.log")


def _log_gl_error(where: str, exc: Exception) -> None:
    with open(_CRASH_LOG, "a") as f:
        f.write(f"\n=== {datetime.datetime.now()} GL error in {where} ===\n")
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)
    traceback.print_exception(type(exc), exc, exc.__traceback__)

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
        self._failed = False
        self._retry_gl = False
        self._last_mouse: tuple[int, int] | None = None

    def _device_size(self) -> tuple[int, int]:
        dpr = self.devicePixelRatio()
        return max(2, int(self.width() * dpr)), max(2, int(self.height() * dpr))

    def initializeGL(self) -> None:
        try:
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
        except Exception as e:  # noqa: BLE001
            self._failed = True
            _log_gl_error("initializeGL", e)

    def resizeGL(self, w: int, h: int) -> None:
        if self.engine:
            self.engine.resize(max(2, w), max(2, h))

    def paintGL(self) -> None:
        if self.engine is None:
            return
        if self._failed:
            if not self._retry_gl:
                return
            self._retry_gl = False
            self._failed = False
            self.makeCurrent()
            self.initializeGL()
            if self._failed:
                self._retry_gl = True          # give it one more try next frame
                return
        try:
            self._paint()
        except Exception as e:  # noqa: BLE001 — log once, keep the window alive
            self._failed = True
            self._retry_gl = True
            _log_gl_error("paintGL", e)

    def _paint(self) -> None:
        # Sync config pulled from the controller
        if self._seen_palette != self.controller.palette_version:
            self.engine.set_palette(self.controller.palette)
            self._seen_palette = self.controller.palette_version
        self.engine.set_preset(self.controller.settings.preset)
        self.engine.settings = self.controller.settings
        self.engine.camera = self.controller.camera

        # Render the visualization into the engine's offscreen FBO
        # Pass None as audio when muted → engine falls back to silent audio
        audio = None if self.controller.muted else self.controller.latest_audio
        self.engine.render(
            audio,
            self.controller.latest_frame,
            self.controller.latest_depth,
        )

        # Capture frame for recording (before blitting so output_fbo is still bound)
        if self.controller.is_recording:
            frame = self.engine.capture_output()
            if frame is not None:
                self.controller.recorder.write_frame(frame)

        # Blit the result to the widget's framebuffer
        screen = self.ctx.detect_framebuffer(self.defaultFramebufferObject())
        screen.use()
        fbw, fbh = self._device_size()
        self.ctx.viewport = (0, 0, fbw, fbh)
        self.engine.output_texture.use(0)
        self.blit_prog["tex"] = 0
        self.blit_vao.render(moderngl.TRIANGLES)

        # Info overlay (painted after GL, works because QOpenGLWidget supports QPainter)
        if self.controller.show_info_overlay:
            self._paint_overlay()

    # ── info overlay ──────────────────────────────────────────────────────────────
    def _paint_overlay(self) -> None:
        """Paint a HUD overlay with BPM, volume, bands, preset, FPS using QPainter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c = self.controller
        a = c.latest_audio
        font = QFont("monospace", 11)
        painter.setFont(font)

        _, _, vw, vh = self.ctx.viewport
        pad = 12
        ly = pad + 16  # line y

        def line(text: str, color: str = "#ffffff") -> None:
            nonlocal ly
            painter.setPen(QColor(color))
            painter.drawText(pad, ly, text)
            ly += 18

        def bar(label: str, val: float, color: str = "#79d3de") -> None:
            nonlocal ly
            bw = min(120, int(val * 120))
            painter.setPen(QColor("#ffffff88"))
            painter.drawText(pad, ly, f"{label}: ")
            painter.setPen(QColor(color))
            painter.drawText(pad + 60, ly, f"{val:.2f}")
            if vw > 200 and bw > 0:
                painter.fillRect(pad + 120, ly - 10, bw, 8, QColor(color))
            ly += 18

        # ── left column ──
        ly = pad + 16
        line(f"🎵 {c.settings.preset}")
        line(f"FPS: {c.settings.fps}")
        if a is not None:
            bpm = f"{a.bpm:.0f}" if a.bpm else "--"
            line(f"BPM: {bpm}")
            bar("Vol", a.volume)
            bar("Bass", a.bands.get("bass", 0))
            bar("Mid",  a.bands.get("mid", 0))
            bar("High", a.bands.get("high", 0))
            bar("Cent", a.spectral_centroid, "#ffcc44")
            bar("Onst", a.onset_strength, "#ff6688")
            line(f"Beat: {'●' if a.beat else '○'}")

        # ── right column: recorded length ──
        if c.is_recording and vw > 360:
            painter.setPen(QColor("#ff4444"))
            elapsed = c.recording_elapsed
            mins, secs = divmod(int(elapsed), 60)
            txt = f"⏺ REC {mins:02d}:{secs:02d}"
            painter.drawText(vw - pad - 100, pad + 16, txt)

        # ── bottom-left mute indicator ──
        if c.muted:
            painter.setPen(QColor("#ff8844"))
            painter.drawText(pad, vh - pad, "🔇 MUTED")

        painter.end()

    # ── 3D camera input (orbit / zoom) ──────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        self._last_mouse = (event.position().x(), event.position().y())

    def mouseMoveEvent(self, event) -> None:
        if self._last_mouse is None:
            return
        x, y = event.position().x(), event.position().y()
        dx, dy = x - self._last_mouse[0], y - self._last_mouse[1]
        self._last_mouse = (x, y)
        self.controller.camera.rotate(dx, -dy)   # screen-y is down → invert
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        self._last_mouse = None

    def wheelEvent(self, event) -> None:
        self.controller.camera.zoom(event.angleDelta().y())
        self.update()

    # ── screenshot ───────────────────────────────────────────────────────────────
    def capture_screenshot(self) -> np.ndarray | None:
        """Return the current rendered frame as (H, W, 4) uint8 RGBA, or None."""
        if self.engine is None or self._failed:
            return None
        self.makeCurrent()
        frame = self.engine.capture_output()
        self.doneCurrent()
        return frame

    def release(self) -> None:
        if self.engine is not None:
            self.makeCurrent()
            self.engine.release()
            if self.blit_vao is not None:
                self.blit_vao.release()
                self.blit_vao = None
            if self.blit_prog is not None:
                self.blit_prog.release()
                self.blit_prog = None
            self.doneCurrent()
            self.engine = None
        self.ctx = None
