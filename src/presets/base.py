"""Preset abstraction.

A preset owns its shaders/buffers and draws into whatever framebuffer the engine
has bound. The engine passes the live AudioData, the current settings, and the
palette LUT texture (a 256x1 RGB gradient) each frame.
"""

from __future__ import annotations

import numpy as np
import moderngl

from src.audio.analyzer import AudioData
from src.config.settings import VisualizerSettings

# Fullscreen triangle (covers the viewport with a single primitive)
_FULLSCREEN_TRI = np.array([-1.0, -1.0, 3.0, -1.0, -1.0, 3.0], dtype="f4")


def fullscreen_vao(ctx: moderngl.Context, program: moderngl.Program) -> moderngl.VertexArray:
    vbo = ctx.buffer(_FULLSCREEN_TRI.tobytes())
    return ctx.vertex_array(program, [(vbo, "2f", "in_pos")])


class Preset:
    name: str = "base"

    def __init__(self, ctx: moderngl.Context) -> None:
        self.ctx = ctx

    def render(
        self,
        audio: AudioData,
        settings: VisualizerSettings,
        palette_lut: moderngl.Texture,
        background: tuple[float, float, float],
    ) -> None:
        raise NotImplementedError

    def release(self) -> None:
        pass
