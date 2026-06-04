"""Threaded webcam / video-file capture with a shared latest-frame buffer.

A single VideoSource is shared by both the preview and fullscreen engines so the
camera is only opened once; each engine uploads the same RGB frame to its own
texture.
"""

from __future__ import annotations

import threading
import time

import cv2
import numpy as np


class VideoSource:
    def __init__(self, spec: int | str, target_fps: float = 30.0) -> None:
        self.spec = spec
        self.is_file = isinstance(spec, str)
        self.target_fps = target_fps
        self.error: str | None = None

        self._cap: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        self._cap = cv2.VideoCapture(self.spec)
        if not self._cap.isOpened():
            self.error = f"cannot open video source {self.spec!r}"
            self._cap = None
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def _loop(self) -> None:
        frame_interval = 1.0 / self.target_fps
        while self._running:
            ok, frame = self._cap.read()
            if not ok:
                if self.is_file:                       # loop the file
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                time.sleep(0.01)
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            with self._lock:
                self._frame = rgb
            if self.is_file:                           # pace file playback
                time.sleep(frame_interval)

    def read(self) -> np.ndarray | None:
        """Return the latest RGB frame (HxWx3 uint8), or None if not ready."""
        with self._lock:
            return self._frame

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
            self._thread = None
        if self._cap:
            self._cap.release()
            self._cap = None
        self._frame = None


def list_cameras(max_devices: int = 6) -> list[int]:
    """Detect connected camera indices.

    On Linux this scans /dev/video* device nodes so it doesn't power on the
    camera (no LED flash) just to enumerate. Falls back to opening devices on
    other platforms.
    """
    import glob
    import re
    import sys

    if sys.platform.startswith("linux"):
        idxs = []
        for node in glob.glob("/dev/video*"):
            m = re.search(r"(\d+)$", node)
            if m:
                idxs.append(int(m.group(1)))
        if idxs:
            return sorted(set(idxs))

    available = []
    for i in range(max_devices):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
        cap.release()
    return available
