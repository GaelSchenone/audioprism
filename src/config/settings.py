"""User-facing visualizer settings, persisted as JSON."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict

CONFIG_PATH = os.path.expanduser("~/.config/audioprism/settings.json")


@dataclass
class VisualizerSettings:
    # Source
    source_index: int | None = None        # sounddevice device index; None = ask
    # Active visuals
    preset: str = "spectrum"
    ui_theme: str = "original"             # drives the Qt interface stylesheet
    graphics_palette: str = "original"     # drives the shader colors (independent)
    # Analysis
    smoothing: float = 0.8                  # 0 = jittery, 1 = frozen
    sensitivity: float = 1.0                # input gain multiplier
    # Rendering
    bloom: float = 0.6                      # 0-1 post-process glow intensity
    background_dim: float = 1.0             # 0-1 multiplier on palette background
    particle_count: int = 20000
    ascii_grid: int = 96                    # ASCII columns (grid definition)
    matrix_density: int = 48                # matrix rain columns
    point_size: float = 1.0                 # point-cloud size multiplier
    fps: int = 60
    # Video source for camera-based presets: int (camera index) or str (file path)
    video_source: int | str = 0
    depth_model: str = "midas"             # 'midas' (fast) or 'depth_anything'
    # New preset params (with defaults so saved settings stay compatible)
    plasma_speed: float = 1.0
    ring_density: int = 12
    kaleidoscope_segments: int = 6
    kaleidoscope_rotation: float = 0.3
    spectrum_mirror: bool = False
    particle_turbulence: float = 0.3
    radial_dual: bool = False
    matrix_charset: str = "procedural"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "VisualizerSettings":
        fields = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in fields})

    def save(self, path: str = CONFIG_PATH) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str = CONFIG_PATH) -> "VisualizerSettings":
        try:
            with open(path) as f:
                return cls.from_dict(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()
