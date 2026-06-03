"""Theme and color-palette data model.

A Palette is an ordered list of control colors. Presets sample it as a smooth
gradient LUT (look-up table) uploaded to the GPU, so any number of control
colors interpolates into a continuous ramp indexed by a value in [0, 1]
(e.g. normalized frequency, particle age, or pixel brightness).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

RGB = tuple[float, float, float]


def parse_color(value: str | tuple[float, float, float] | list) -> RGB:
    """Accept '#rrggbb', '#rgb', 'r,g,b' (0-255), or an (r,g,b) tuple in 0-1."""
    if isinstance(value, (tuple, list)):
        r, g, b = (float(c) for c in value[:3])
        # Heuristic: values >1 are assumed 0-255
        if max(r, g, b) > 1.0:
            return (r / 255.0, g / 255.0, b / 255.0)
        return (r, g, b)

    s = value.strip().lstrip("#")
    if "," in s:  # 'r,g,b' in 0-255
        parts = [int(p) for p in s.split(",")]
        return (parts[0] / 255.0, parts[1] / 255.0, parts[2] / 255.0)
    if len(s) == 3:  # '#rgb'
        s = "".join(c * 2 for c in s)
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return (r, g, b)


@dataclass
class Palette:
    name: str
    colors: list[RGB]                       # ordered control colors (0-1)
    background: RGB = (0.02, 0.02, 0.03)
    accent: RGB | None = None               # UI highlight; defaults to colors[-1]

    def __post_init__(self) -> None:
        self.colors = [parse_color(c) for c in self.colors]
        self.background = parse_color(self.background)
        if self.accent is None:
            self.accent = self.colors[-1] if self.colors else (1.0, 1.0, 1.0)
        else:
            self.accent = parse_color(self.accent)

    def sample(self, t: float) -> RGB:
        """Linearly interpolate the palette at position t in [0, 1]."""
        if len(self.colors) == 1:
            return self.colors[0]
        t = min(max(t, 0.0), 1.0)
        pos = t * (len(self.colors) - 1)
        i = int(pos)
        frac = pos - i
        if i >= len(self.colors) - 1:
            return self.colors[-1]
        a, b = self.colors[i], self.colors[i + 1]
        return (
            a[0] + (b[0] - a[0]) * frac,
            a[1] + (b[1] - a[1]) * frac,
            a[2] + (b[2] - a[2]) * frac,
        )

    def to_lut(self, size: int = 256) -> np.ndarray:
        """Return an (size, 3) float32 gradient for upload as a 1D GL texture."""
        arr = np.asarray(self.colors, dtype=np.float32)
        if len(arr) == 1:
            return np.repeat(arr, size, axis=0)
        src_pos = np.linspace(0.0, 1.0, len(arr), dtype=np.float32)
        dst_pos = np.linspace(0.0, 1.0, size, dtype=np.float32)
        lut = np.empty((size, 3), dtype=np.float32)
        for ch in range(3):
            lut[:, ch] = np.interp(dst_pos, src_pos, arr[:, ch])
        return lut


class ThemeRegistry:
    """Holds all available palettes, looked up by name."""

    def __init__(self) -> None:
        self._palettes: dict[str, Palette] = {}

    def register(self, palette: Palette) -> None:
        self._palettes[palette.name] = palette

    def register_many(self, data: list[dict]) -> None:
        """Bulk-load palettes from dicts: {name, colors, background?, accent?}."""
        for entry in data:
            self.register(
                Palette(
                    name=entry["name"],
                    colors=entry["colors"],
                    background=entry.get("background", (0.02, 0.02, 0.03)),
                    accent=entry.get("accent"),
                )
            )

    def get(self, name: str) -> Palette:
        if name not in self._palettes:
            return next(iter(self._palettes.values()))
        return self._palettes[name]

    def names(self) -> list[str]:
        return list(self._palettes)

    def __len__(self) -> int:
        return len(self._palettes)


# ── Placeholder palettes ──────────────────────────────────────────────────────
# Replaced/extended by the user's 16 themes via ThemeRegistry.register_many().
_DEFAULTS = [
    {"name": "Spectrum",  "colors": ["#0d1b2a", "#1b4965", "#5fa8d3", "#cae9ff"]},
    {"name": "Synthwave", "colors": ["#2b0f54", "#ab1f6f", "#ff5f6d", "#ffc371"],
     "background": "#1a0933"},
    {"name": "Mono",      "colors": ["#000000", "#7a7a7a", "#ffffff"]},
]


def default_registry() -> ThemeRegistry:
    reg = ThemeRegistry()
    reg.register_many(_DEFAULTS)
    return reg
