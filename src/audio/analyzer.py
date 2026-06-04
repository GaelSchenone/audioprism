"""FFT analysis, per-band energies, beat detection, BPM estimation."""

import time
import numpy as np
from dataclasses import dataclass, field

SAMPLE_RATE = 44100
FFT_SIZE = 2048
SMOOTHING = 0.8
BEAT_THRESHOLD = 1.5
# Refractory period between beats — caps detection at ~300 BPM and stops the
# detector from firing on near-every frame during sustained loud passages.
MIN_BEAT_INTERVAL = 0.20
# ~1 s of energy history at 44100 / 1024 fps
BEAT_HISTORY_LEN = 43

BAND_RANGES: dict[str, tuple[int, int]] = {
    "sub_bass": (20,    60),
    "bass":     (60,   250),
    "mid":      (250,  2000),
    "high_mid": (2000, 6000),
    "high":     (6000, 20000),
}


@dataclass
class AudioData:
    waveform: np.ndarray        # raw samples, length FFT_SIZE
    spectrum: np.ndarray        # normalized magnitude (0–1), length FFT_SIZE//2+1
    frequencies: np.ndarray     # Hz value per spectrum bin
    bands: dict[str, float]     # per-band mean energy (0–1)
    volume: float               # RMS volume (0–1)
    beat: bool                  # True on the frame a beat is detected
    bpm: float                  # estimated BPM (0.0 until enough beats sampled)


class AudioAnalyzer:
    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self._smoothed = np.zeros(FFT_SIZE // 2 + 1, dtype=np.float32)
        self._energy_history = np.zeros(BEAT_HISTORY_LEN, dtype=np.float64)
        self._beat_times: list[float] = []
        self._last_beat_time: float = 0.0
        self._bpm: float = 0.0
        self.frequencies = np.fft.rfftfreq(FFT_SIZE, 1.0 / sample_rate).astype(np.float32)
        self._window = np.hanning(FFT_SIZE).astype(np.float32)

    def analyze(self, samples: np.ndarray) -> AudioData:
        # Pad / trim to FFT_SIZE
        frame = np.zeros(FFT_SIZE, dtype=np.float32)
        n = min(len(samples), FFT_SIZE)
        frame[:n] = samples[:n]

        # Windowed FFT → magnitude
        fft_mag = np.abs(np.fft.rfft(frame * self._window)).astype(np.float32) / FFT_SIZE

        # Exponential smoothing
        self._smoothed[:] = SMOOTHING * self._smoothed + (1.0 - SMOOTHING) * fft_mag

        # Normalize to 0–1
        peak = self._smoothed.max()
        spectrum = self._smoothed / peak if peak > 1e-9 else self._smoothed.copy()

        # RMS volume, scaled so typical listening sits in 0.2–0.8
        volume = float(np.clip(np.sqrt(np.mean(frame ** 2)) * 10.0, 0.0, 1.0))

        # Per-band mean energy
        bands: dict[str, float] = {}
        for name, (lo, hi) in BAND_RANGES.items():
            mask = (self.frequencies >= lo) & (self.frequencies <= hi)
            bands[name] = float(spectrum[mask].mean()) if mask.any() else 0.0

        # Beat detection: instantaneous energy above the local mean, gated by a
        # refractory period so sustained loud passages don't fire every frame.
        energy = float(np.mean(fft_mag ** 2))
        mean_energy = float(self._energy_history.mean())
        now = time.monotonic()
        beat = (
            energy > BEAT_THRESHOLD * mean_energy
            and energy > 1e-10
            and (now - self._last_beat_time) > MIN_BEAT_INTERVAL
        )
        self._energy_history = np.roll(self._energy_history, 1)
        self._energy_history[0] = energy

        # BPM from inter-beat intervals (last 10 s window)
        if beat:
            self._last_beat_time = now
            self._beat_times.append(now)
            self._beat_times = [t for t in self._beat_times if now - t <= 10.0]
            if len(self._beat_times) >= 4:
                intervals = np.diff(self._beat_times[-8:])
                mean_ibi = float(intervals.mean())
                if mean_ibi > 0:
                    self._bpm = 60.0 / mean_ibi

        return AudioData(
            waveform=frame,
            spectrum=spectrum,
            frequencies=self.frequencies,
            bands=bands,
            volume=volume,
            beat=beat,
            bpm=self._bpm,
        )
