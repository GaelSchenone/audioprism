"""Audio capture thread with lock-free ring buffer."""

import threading
import numpy as np
import sounddevice as sd
from collections import deque

BLOCK_SIZE = 1024
CHANNELS = 1
_PREFERRED_RATES = (48000, 44100, 22050)


def _detect_sample_rate(device: int | str | None) -> int:
    """Return the device's default sample rate, falling back through common rates."""
    info = sd.query_devices(device, kind="input")
    rate = int(info["default_samplerate"])
    if rate > 0:
        return rate
    for r in _PREFERRED_RATES:
        try:
            sd.check_input_settings(device=device, samplerate=r, channels=CHANNELS)
            return r
        except Exception:
            continue
    return 48000


class AudioCapture:
    def __init__(
        self,
        device: int | str | None = None,
        sample_rate: int | None = None,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate or _detect_sample_rate(device)
        self._buffer: deque[np.ndarray] = deque(maxlen=16)
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._stream = sd.InputStream(
            device=self.device,
            samplerate=self.sample_rate,
            channels=CHANNELS,
            blocksize=BLOCK_SIZE,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time,  # noqa: ANN001
        status: sd.CallbackFlags,
    ) -> None:
        with self._lock:
            self._buffer.append(indata[:, 0].copy())

    def read(self) -> np.ndarray | None:
        """Return the most recent block of samples, or None if buffer is empty."""
        with self._lock:
            return self._buffer[-1].copy() if self._buffer else None

    def stop(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
