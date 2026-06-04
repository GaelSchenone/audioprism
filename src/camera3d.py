"""Orbit camera for the 3D presets.

Holds orbit state (yaw/pitch/distance around a target) and produces an MVP
matrix. Mouse drag rotates, scroll zooms. The matrix follows the pyrr row-vector
convention; uploaded as-is to moderngl it pairs with `gl_Position = mvp * vec4(pos,1)`
in the shader (row-major storage + GLSL column-major read cancel out).
"""

from __future__ import annotations

import numpy as np
from pyrr import matrix44


class Camera3D:
    def __init__(self) -> None:
        self.yaw = 0.6
        self.pitch = 0.35
        self.distance = 3.2
        self.target = np.array([0.0, 0.0, 0.0], dtype="f4")
        self.fov = 50.0
        self.near = 0.1
        self.far = 100.0
        self.min_distance = 1.0
        self.max_distance = 15.0

    def reset(self) -> None:
        self.yaw = 0.6
        self.pitch = 0.35
        self.distance = 3.2
        self.target[:] = 0.0

    def rotate(self, dx: float, dy: float, speed: float = 0.006) -> None:
        self.yaw += dx * speed
        self.pitch += dy * speed
        limit = np.pi / 2 - 0.05
        self.pitch = float(np.clip(self.pitch, -limit, limit))

    def zoom(self, delta: float, speed: float = 0.0012) -> None:
        # delta = wheel angleDelta().y() (±120 per notch); up → zoom in
        self.distance *= float(np.exp(-delta * speed))
        self.distance = float(np.clip(self.distance, self.min_distance, self.max_distance))

    def eye(self) -> np.ndarray:
        cp = np.cos(self.pitch)
        offset = np.array(
            [cp * np.sin(self.yaw), np.sin(self.pitch), cp * np.cos(self.yaw)],
            dtype="f4",
        )
        return self.target + offset * self.distance

    def mvp(self, aspect: float) -> np.ndarray:
        proj = matrix44.create_perspective_projection_matrix(
            self.fov, max(aspect, 1e-3), self.near, self.far, dtype="f4"
        )
        view = matrix44.create_look_at(
            self.eye(), self.target, np.array([0.0, 1.0, 0.0], dtype="f4"), dtype="f4"
        )
        return matrix44.multiply(view, proj).astype("f4")
