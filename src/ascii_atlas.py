"""Reusable ASCII glyph atlas for the ASCII presets.

Renders a density ramp of characters (sparse → dense) into a horizontal strip
texture. The shader maps a 0–1 brightness/coverage value to a glyph index and
samples that cell, giving real typographic ASCII output. Shared by ascii_bars
and (later) ascii_cam.
"""

from __future__ import annotations

import os

import moderngl
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Characters ordered by increasing ink density (index 0 = blank).
DEFAULT_RAMP = " .:-=+*#%@"

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/ttf-bitstream-vera/VeraMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


class AsciiAtlas:
    def __init__(self, ramp: str = DEFAULT_RAMP, cell_w: int = 16, cell_h: int = 24) -> None:
        self.ramp = ramp
        self.n = len(ramp)
        self.cell_w = cell_w
        self.cell_h = cell_h

        font = _load_font(int(cell_h * 0.9))
        img = Image.new("L", (cell_w * self.n, cell_h), 0)
        draw = ImageDraw.Draw(img)
        for i, ch in enumerate(ramp):
            bbox = draw.textbbox((0, 0), ch, font=font)
            gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = i * cell_w + (cell_w - gw) // 2 - bbox[0]
            y = (cell_h - gh) // 2 - bbox[1]
            draw.text((x, y), ch, fill=255, font=font)

        arr = np.asarray(img, dtype=np.uint8)
        # Flip vertically so GL texture v-axis matches screen-up orientation.
        self.data = np.ascontiguousarray(np.flipud(arr))

    def texture(self, ctx: moderngl.Context) -> moderngl.Texture:
        tex = ctx.texture((self.cell_w * self.n, self.cell_h), 1, self.data.tobytes())
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        return tex
