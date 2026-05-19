"""
Feedback detection engine.

Detection is three-stage:
  1. Peak finder   — locate narrow spectral spikes
  2. Onset tracker — confirm the spike is growing (not a transient)
  3. Confidence    — require sustained growth across N frames

Only frequencies that pass all three stages are returned as confirmed feedback.
"""

import time
import numpy as np
from dataclasses import dataclass, field
from scipy.signal import find_peaks
from typing import Optional


@dataclass
class CandidateFreq:
    frequency: float
    magnitude_db: float
    first_seen: float = field(default_factory=time.time)
    frames_growing: int = 0
    frames_sustained: int = 0
    peak_db: float = -96.0
    confirmed: bool = False

    @property
    def age_ms(self):
        return (time.time() - self.first_seen) * 1000


class FeedbackDetector:
    def __init__(
        self,
        sample_rate: float = 48000,
        fft_size: int = 4096,
        threshold_db: float = -30.0,
        prominence_db: float = 12.0,
        growth_rate_db_per_frame: float = 1.5,
        confirm_frames: int = 3,
        freq_min: float = 80.0,
        freq_max: float = 16000.0,
    ):
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.threshold_db = threshold_db
        self.prominence_db = prominence_db
        self.growth_rate_db_per_frame = growth_rate_db_per_frame
        self.confirm_frames = confirm_frames
        self.freq_min = freq_min
        self.freq_max = freq_max

        self.frequencies = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
        self._candidates: dict[float, CandidateFreq] = {}
        self._prev_magnitude_db: Optional[np.ndarray] = None

        # History for AI learning
        self.event_log: list[dict] = []

    def analyze(self, magnitude_db: np.ndarray) -> list[float]:
        """
        Feed a magnitude spectrum; returns list of confirmed feedback frequencies (Hz).
        """
        freqs = self.frequencies
        band_mask = (freqs >= self.freq_min) & (freqs <= self.freq_max)
        band_mag = magnitude_db.copy()
        band_mag[~band_mask] = -96.0

        # --- Stage 1: find narrow prominent peaks ---
        peaks, props = find_peaks(
            band_mag,
            height=self.threshold_db,
            prominence=self.prominence_db,
            width=(1, 8),   # narrow band in FFT bins
        )

        peak_freqs = {float(freqs[p]): float(band_mag[p]) for p in peaks}

        # --- Stage 2: onset velocity check ---
        growing_freqs = set()
        if self._prev_magnitude_db is not None:
            for pf, pm in peak_freqs.items():
                bin_idx = np.argmin(np.abs(freqs - pf))
                delta = pm - float(self._prev_magnitude_db[bin_idx])
                if delta >= self.growth_rate_db_per_frame:
                    growing_freqs.add(pf)

        self._prev_magnitude_db = magnitude_db.copy()

        # --- Stage 3: confidence accumulation ---
        confirmed = []
        matched_keys = set()

        for pf, pm in peak_freqs.items():
            key = self._nearest_candidate_key(pf)
            if key is None:
                self._candidates[pf] = CandidateFreq(frequency=pf, magnitude_db=pm)
                key = pf

            matched_keys.add(key)
            cand = self._candidates[key]
            cand.magnitude_db = pm
            cand.peak_db = max(cand.peak_db, pm)

            if pf in growing_freqs:
                cand.frames_growing += 1
                cand.frames_sustained += 1
            else:
                cand.frames_sustained = max(0, cand.frames_sustained - 1)

            if cand.frames_growing >= self.confirm_frames and not cand.confirmed:
                cand.confirmed = True
                self.event_log.append({
                    "time": time.time(),
                    "frequency": cand.frequency,
                    "magnitude_db": cand.magnitude_db,
                })

            if cand.confirmed:
                confirmed.append(cand.frequency)

        # Expire old candidates
        stale = [k for k in self._candidates if k not in matched_keys]
        for k in stale:
            self._candidates[k].frames_growing = max(0, self._candidates[k].frames_growing - 1)
            if self._candidates[k].frames_growing == 0:
                self._candidates[k].confirmed = False
                del self._candidates[k]

        return confirmed

    def _nearest_candidate_key(self, freq: float, tolerance: float = 0.05) -> Optional[float]:
        for k in self._candidates:
            if abs(k - freq) / freq < tolerance:
                return k
        return None

    def get_candidates(self) -> list[CandidateFreq]:
        return list(self._candidates.values())

    def reset(self):
        self._candidates.clear()
        self._prev_magnitude_db = None
