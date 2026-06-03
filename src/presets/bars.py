"""Shared log-frequency binning used by the bar-style presets."""

from __future__ import annotations

import numpy as np


def make_log_bins(
    freqs: np.ndarray,
    nbars: int,
    fmin: float = 30.0,
    fmax: float = 16000.0,
) -> np.ndarray:
    """Return NBARS+1 spectrum-bin indices marking log-spaced band edges."""
    edges = np.logspace(np.log10(fmin), np.log10(fmax), nbars + 1)
    return np.clip(np.searchsorted(freqs, edges).astype(np.int64), 0, len(freqs) - 1)


def bars_from_spectrum(spectrum: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Max-reduce the spectrum into per-bar magnitudes using bin edges `idx`."""
    return np.maximum.reduceat(spectrum, idx[:-1])
