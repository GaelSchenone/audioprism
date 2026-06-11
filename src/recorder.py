"""Video recording: captures RGBA frames and writes an MP4 via OpenCV.

The recorder runs synchronously on the calling thread (the Qt paint thread),
so frame writes are expected to be fast enough at 30-60 fps.  Encoding is
done by OpenCV's VideoWriter on the same thread — for high-res or high-fps
recordings a background-encoder variant could be added later.
"""

from __future__ import annotations

import cv2
import numpy as np


class VideoRecorder:
    """Writes RGBA frames to a video file.

    Parameters
    ----------
    path : str
        Output file path (should end in .mp4).
    fps : float
        Frames per second for the output.
    width, height : int
        Frame dimensions in pixels.
    """

    def __init__(self, path: str, fps: float, width: int, height: int) -> None:
        self.path = path
        self.fps = max(1.0, fps)
        self.width = width
        self.height = height
        self._writer: cv2.VideoWriter | None = None
        self._frame_count = 0
        self._open()

    def _open(self) -> None:
        fourcc = self._pick_fourcc()
        self._writer = cv2.VideoWriter(
            self.path, fourcc, self.fps, (self.width, self.height)
        )
        if not self._writer or not self._writer.isOpened():
            raise RuntimeError(
                f"Failed to open video writer for {self.path!r} "
                f"(codec {fourcc}, {self.width}x{self.height} @ {self.fps}fps)"
            )

    @staticmethod
    def _pick_fourcc() -> int:
        """Return the first working fourcc code, preferring H.264."""
        for codec in ("mp4v", "avc1", "XVID", "MJPG"):
            c = cv2.VideoWriter_fourcc(*codec)
            if c:
                return c
        return 0  # shouldn't happen — at least one of the above exists

    def write_frame(self, frame_rgba: np.ndarray) -> None:
        """Encode & write one RGBA uint8 frame.

        Frames whose dimensions don't match the initial ``(width, height)``
        are silently skipped (handles mid-recording resize gracefully).
        """
        if self._writer is None:
            return
        h, w = frame_rgba.shape[:2]
        if (w, h) != (self.width, self.height):
            return
        # OpenCV expects BGR order
        bgr = cv2.cvtColor(frame_rgba, cv2.COLOR_RGBA2BGR)
        self._writer.write(bgr)
        self._frame_count += 1

    @property
    def elapsed(self) -> float:
        """Duration recorded so far (seconds)."""
        return self._frame_count / self.fps if self.fps > 0 else 0.0

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def close(self) -> None:
        """Finalise the video file and release resources."""
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def __del__(self) -> None:
        self.close()
