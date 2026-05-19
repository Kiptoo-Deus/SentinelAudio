"""
Biquad IIR notch filter bank.
Each notch is a second-order section with high Q to produce
a narrow, surgical cut. Filters are applied in-place on the
software monitor path (not the main PA signal path).
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class NotchFilter:
    frequency: float
    sample_rate: float
    Q: float = 50.0
    depth_db: float = 0.0          # how deep the notch is right now (grows toward target)
    target_depth_db: float = -18.0
    channel: Optional[int] = None  # XR16 channel that caused this (None = global)
    created_at: float = field(default_factory=time.time)
    last_triggered: float = field(default_factory=time.time)
    active: bool = True

    # biquad state
    x1: float = 0.0
    x2: float = 0.0
    y1: float = 0.0
    y2: float = 0.0

    def _coeffs(self):
        w0 = 2 * np.pi * self.frequency / self.sample_rate
        # Scale Q by current depth so shallow cuts are wider
        effective_Q = self.Q * (abs(self.depth_db) / max(abs(self.target_depth_db), 1.0) + 0.1)
        alpha = np.sin(w0) / (2 * effective_Q)
        cos_w0 = np.cos(w0)

        linear_gain = 10 ** (self.depth_db / 20.0)
        # Notch with gain at center
        b0 = 1.0
        b1 = -2.0 * cos_w0
        b2 = 1.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
        return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)

    def process(self, x: np.ndarray) -> np.ndarray:
        b0, b1, b2, a1, a2 = self._coeffs()
        y = np.empty_like(x)
        x1, x2, y1, y2 = self.x1, self.x2, self.y1, self.y2
        for n, xn in enumerate(x):
            yn = b0 * xn + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1 = x1, xn
            y2, y1 = y1, yn
            y[n] = yn
        self.x1, self.x2, self.y1, self.y2 = x1, x2, y1, y2
        return y

    def deepen(self, step_db: float = 2.0):
        self.depth_db = max(self.target_depth_db, self.depth_db - step_db)
        self.last_triggered = time.time()

    def release(self, step_db: float = 1.0):
        self.depth_db = min(0.0, self.depth_db + step_db)
        if self.depth_db >= 0.0:
            self.active = False

    @property
    def age_seconds(self):
        return time.time() - self.created_at

    @property
    def idle_seconds(self):
        return time.time() - self.last_triggered


class NotchFilterBank:
    MAX_FILTERS = 32

    def __init__(self, sample_rate: float = 48000.0):
        self.sample_rate = sample_rate
        self.filters: list[NotchFilter] = []

    def add_or_update(self, frequency: float, channel: Optional[int] = None,
                      Q: float = 50.0, target_db: float = -18.0) -> NotchFilter:
        # Check if a filter already exists near this frequency (±5%)
        for f in self.filters:
            if f.active and abs(f.frequency - frequency) / frequency < 0.05:
                f.deepen()
                f.last_triggered = time.time()
                return f

        if len([f for f in self.filters if f.active]) >= self.MAX_FILTERS:
            # Replace oldest idle filter
            idle = sorted(
                [f for f in self.filters if f.active],
                key=lambda f: f.idle_seconds,
                reverse=True,
            )
            if idle:
                idle[0].active = False

        nf = NotchFilter(
            frequency=frequency,
            sample_rate=self.sample_rate,
            Q=Q,
            target_depth_db=target_db,
            depth_db=-3.0,  # start shallow and deepen
            channel=channel,
        )
        self.filters.append(nf)
        return nf

    def process(self, audio: np.ndarray) -> np.ndarray:
        out = audio.copy()
        for f in self.filters:
            if f.active:
                out = f.process(out)
        return out

    def tick_release(self, feedback_freqs: set):
        """Called each analysis frame — release filters whose feedback has stopped."""
        for f in self.filters:
            if not f.active:
                continue
            still_feeding = any(abs(f.frequency - ff) / f.frequency < 0.05 for ff in feedback_freqs)
            if still_feeding:
                f.deepen(1.0)
            elif f.idle_seconds > 2.0:
                f.release(0.5)

        self.filters = [f for f in self.filters if f.active or f.depth_db < 0.0]

    @property
    def active_filters(self) -> list[NotchFilter]:
        return [f for f in self.filters if f.active]
