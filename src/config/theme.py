"""Theme system: UI themes (Qt stylesheet) + graphics palettes (shaders).

The 16 built-in themes define UI role colors (bg / fg / accent / red / green /
border). Each also yields a *graphics palette* — an ordered gradient the
shaders sample as a LUT — derived from its ink colors but tracked independently,
so the visualization colors can be changed (and custom palettes saved) without
touching the UI look.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np

RGB = tuple[float, float, float]

CUSTOM_PALETTES_PATH = os.path.expanduser("~/.config/audioprism/palettes.json")


# ── color helpers ──────────────────────────────────────────────────────────────

def parse_color(value: str | tuple[float, float, float] | list) -> RGB:
    """Accept '#rrggbb', '#rgb', 'r,g,b' (0-255), or an (r,g,b) tuple in 0-1."""
    if isinstance(value, (tuple, list)):
        r, g, b = (float(c) for c in value[:3])
        if max(r, g, b) > 1.0:
            return (r / 255.0, g / 255.0, b / 255.0)
        return (r, g, b)

    s = value.strip().lstrip("#")
    if "," in s:
        parts = [int(p) for p in s.split(",")]
        return (parts[0] / 255.0, parts[1] / 255.0, parts[2] / 255.0)
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0)


def to_hex(rgb: RGB) -> str:
    return "#" + "".join(f"{int(round(c * 255)):02x}" for c in rgb)


def _luminance(rgb: RGB) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _dedup(colors: list[RGB]) -> list[RGB]:
    """Drop near-duplicate colors while preserving order."""
    out: list[RGB] = []
    for c in colors:
        key = tuple(round(v, 3) for v in c)
        if all(tuple(round(v, 3) for v in o) != key for o in out):
            out.append(c)
    return out


# ── graphics palette ───────────────────────────────────────────────────────────

@dataclass
class Palette:
    name: str
    colors: list[RGB]                       # ordered control colors (0-1)
    background: RGB = (0.02, 0.02, 0.03)
    accent: RGB | None = None
    custom: bool = False

    def __post_init__(self) -> None:
        self.colors = [parse_color(c) for c in self.colors]
        self.background = parse_color(self.background)
        self.accent = parse_color(self.accent) if self.accent is not None else self.colors[-1]

    def sample(self, t: float) -> RGB:
        if len(self.colors) == 1:
            return self.colors[0]
        t = min(max(t, 0.0), 1.0)
        pos = t * (len(self.colors) - 1)
        i = int(pos)
        if i >= len(self.colors) - 1:
            return self.colors[-1]
        frac = pos - i
        a, b = self.colors[i], self.colors[i + 1]
        return (a[0] + (b[0] - a[0]) * frac,
                a[1] + (b[1] - a[1]) * frac,
                a[2] + (b[2] - a[2]) * frac)

    def to_lut(self, size: int = 256) -> np.ndarray:
        """Return an (size, 3) float32 gradient for upload as a 1D GL texture."""
        arr = np.asarray(self.colors, dtype=np.float32)
        if len(arr) == 1:
            return np.repeat(arr, size, axis=0)
        src = np.linspace(0.0, 1.0, len(arr), dtype=np.float32)
        dst = np.linspace(0.0, 1.0, size, dtype=np.float32)
        lut = np.empty((size, 3), dtype=np.float32)
        for ch in range(3):
            lut[:, ch] = np.interp(dst, src, arr[:, ch])
        return lut

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "colors": [to_hex(c) for c in self.colors],
            "background": to_hex(self.background),
            "accent": to_hex(self.accent),
        }


# ── UI theme ─────────────────────────────────────────────────────────────────

@dataclass
class UITheme:
    name: str
    bg: RGB
    fg: RGB
    accent: RGB
    red: RGB
    green: RGB
    border: RGB

    def __post_init__(self) -> None:
        for field_name in ("bg", "fg", "accent", "red", "green", "border"):
            setattr(self, field_name, parse_color(getattr(self, field_name)))

    def qss(self) -> str:
        """Generate a Qt stylesheet from the role colors."""
        bg, fg = to_hex(self.bg), to_hex(self.fg)
        accent, border = to_hex(self.accent), to_hex(self.border)
        # Panel slightly offset from the pure background for separation
        panel = to_hex(tuple(c * 0.85 + 0.04 for c in self.bg))
        return f"""
        QWidget {{ background: {bg}; color: {fg}; font-size: 12px; }}
        QGroupBox {{ border: 1px solid {border}; border-radius: 6px;
                     margin-top: 10px; padding: 8px; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 8px;
                            color: {accent}; }}
        QPushButton {{ background: {panel}; border: 1px solid {border};
                       border-radius: 5px; padding: 5px 12px; }}
        QPushButton:hover {{ border-color: {accent}; }}
        QPushButton:pressed {{ background: {accent}; color: {bg}; }}
        QComboBox {{ background: {panel}; border: 1px solid {border};
                     border-radius: 5px; padding: 4px 8px; }}
        QComboBox QAbstractItemView {{ background: {panel};
                                       selection-background-color: {accent};
                                       selection-color: {bg}; }}
        QSlider::groove:horizontal {{ height: 4px; background: {border};
                                      border-radius: 2px; }}
        QSlider::handle:horizontal {{ background: {accent}; width: 14px;
                                      margin: -6px 0; border-radius: 7px; }}
        QLabel {{ background: transparent; }}
        """


# ── 16 built-in themes ─────────────────────────────────────────────────────────

_THEME_SPECS: list[dict] = [
    {"name": "original",  "bg": "#202328", "fg": "#79d3de", "accent": "#e8707a", "red": "#e8707a", "green": "#79d3de", "border": "#454b54"},
    {"name": "light",     "bg": "#f8f8f2", "fg": "#5a5a54", "accent": "#c88a67", "red": "#c88a67", "green": "#7a9a7a", "border": "#c8cccd"},
    {"name": "midnight",  "bg": "#11161d", "fg": "#c5d2d9", "accent": "#ee5e5e", "red": "#ee5e5e", "green": "#7ab8c0", "border": "#2a3543"},
    {"name": "paper",     "bg": "#ffffff", "fg": "#3a3a3a", "accent": "#d5b85a", "red": "#d5b85a", "green": "#7a9a6a", "border": "#d8d8d8"},
    {"name": "cyberpunk", "bg": "#080a0f", "fg": "#00ffff", "accent": "#ff00ff", "red": "#ff00ff", "green": "#00ffaa", "border": "#2a0050"},
    {"name": "retrowave", "bg": "#1a1c35", "fg": "#c8d0e0", "accent": "#e85278", "red": "#e85278", "green": "#5ac8a0", "border": "#353870"},
    {"name": "forest",    "bg": "#132019", "fg": "#9bd29d", "accent": "#77c681", "red": "#77c681", "green": "#77c681", "border": "#2e4a38"},
    {"name": "ocean",     "bg": "#0b1b2b", "fg": "#78c2ff", "accent": "#479bff", "red": "#479bff", "green": "#5ad0a0", "border": "#1a3d5a"},
    {"name": "ume",       "bg": "#1a1423", "fg": "#e4b6d5", "accent": "#f3c7e3", "red": "#f3c7e3", "green": "#a8c090", "border": "#403050"},
    {"name": "copper",    "bg": "#1a1310", "fg": "#deae92", "accent": "#d07a54", "red": "#d07a54", "green": "#8ab080", "border": "#382c25"},
    {"name": "terminal",  "bg": "#000000", "fg": "#00ff00", "accent": "#00ff00", "red": "#00cc00", "green": "#00ff00", "border": "#003300"},
    {"name": "organs",    "bg": "#140a0a", "fg": "#e6dac7", "accent": "#d24a4a", "red": "#d24a4a", "green": "#8aaa7a", "border": "#331a1a"},
    {"name": "lavender",  "bg": "#322845", "fg": "#c8b8e8", "accent": "#a08adf", "red": "#a08adf", "green": "#80b090", "border": "#4c3e64"},
    {"name": "gpt",       "bg": "#1a1a1a", "fg": "#cccccc", "accent": "#a3a3a3", "red": "#a3a3a3", "green": "#7aaa7a", "border": "#3a3a3a"},
    {"name": "claude",    "bg": "#201e1d", "fg": "#d4ccc4", "accent": "#d87656", "red": "#d87656", "green": "#7aaa7a", "border": "#46413e"},
    {"name": "cute",      "bg": "#ffffff", "fg": "#6a3a4a", "accent": "#ff6699", "red": "#ff6699", "green": "#80b080", "border": "#f0d0da"},
]


def _derive_palette(ui: UITheme) -> Palette:
    """Build a graphics gradient from a UI theme's ink colors, low→high luminance."""
    ink = _dedup([ui.accent, ui.red, ui.green, ui.fg])
    ink.sort(key=_luminance)
    return Palette(name=ui.name, colors=ink, background=ui.bg, accent=ui.accent)


# ── registry ───────────────────────────────────────────────────────────────────

class ThemeRegistry:
    def __init__(self, load_customs: bool = True) -> None:
        self.ui_themes: dict[str, UITheme] = {}
        self.palettes: dict[str, Palette] = {}
        for spec in _THEME_SPECS:
            ui = UITheme(**spec)
            self.ui_themes[ui.name] = ui
            self.palettes[ui.name] = _derive_palette(ui)
        if load_customs:
            self._load_customs()

    # UI themes
    def get_ui(self, name: str) -> UITheme:
        return self.ui_themes.get(name, next(iter(self.ui_themes.values())))

    def ui_names(self) -> list[str]:
        return list(self.ui_themes)

    # Graphics palettes
    def get_palette(self, name: str) -> Palette:
        return self.palettes.get(name, next(iter(self.palettes.values())))

    def palette_names(self) -> list[str]:
        return list(self.palettes)

    def add_palette(self, palette: Palette, save: bool = True) -> None:
        palette.custom = True
        self.palettes[palette.name] = palette
        if save:
            self.save_customs()

    def remove_palette(self, name: str) -> None:
        pal = self.palettes.get(name)
        if pal and pal.custom:
            del self.palettes[name]
            self.save_customs()

    # Persistence of custom palettes
    def save_customs(self, path: str = CUSTOM_PALETTES_PATH) -> None:
        customs = [p.to_dict() for p in self.palettes.values() if p.custom]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(customs, f, indent=2)

    def _load_customs(self, path: str = CUSTOM_PALETTES_PATH) -> None:
        try:
            with open(path) as f:
                entries = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        for e in entries:
            self.palettes[e["name"]] = Palette(
                name=e["name"],
                colors=e["colors"],
                background=e.get("background", (0.02, 0.02, 0.03)),
                accent=e.get("accent"),
                custom=True,
            )


def default_registry() -> ThemeRegistry:
    return ThemeRegistry()
