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
    fps: int = 60

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
