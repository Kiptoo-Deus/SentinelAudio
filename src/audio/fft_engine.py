"""
Real-time FFT analysis engine.
Converts audio buffers into frequency-magnitude spectra using
a Hann window and overlap-add accumulation for smooth display.
"""

import numpy as np
from scipy.signal import windows


class FFTEngine:
    def __init__(self, fft_size=4096, sample_rate=48000, smoothing=0.75):
        self.fft_size = fft_size
        self.sample_rate = sample_rate
        self.smoothing = smoothing

        self._window = windows.hann(fft_size)
        self._accumulator = np.zeros(fft_size, dtype=np.float32)
        self._write_pos = 0

        n_bins = fft_size // 2 + 1
        self.frequencies = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
        self._smoothed_magnitude_db = np.full(n_bins, -96.0)

    def process(self, audio_chunk: np.ndarray) -> np.ndarray:
        """Feed a mono float32 chunk; returns smoothed magnitude in dB."""
        chunk = audio_chunk.astype(np.float32)
        n = len(chunk)

        space = self.fft_size - self._write_pos
        if n >= space:
            self._accumulator[self._write_pos:] = chunk[:space]
            self._run_fft()
            remaining = chunk[space:]
            self._accumulator[:len(remaining)] = remaining
            self._write_pos = len(remaining)
        else:
            self._accumulator[self._write_pos:self._write_pos + n] = chunk
            self._write_pos += n

        return self._smoothed_magnitude_db.copy()

    def _run_fft(self):
        windowed = self._accumulator * self._window
        spectrum = np.fft.rfft(windowed)
        magnitude = np.abs(spectrum) / (self.fft_size / 2)
        magnitude_db = 20 * np.log10(magnitude + 1e-10)
        np.clip(magnitude_db, -96.0, 0.0, out=magnitude_db)

        self._smoothed_magnitude_db = (
            self.smoothing * self._smoothed_magnitude_db
            + (1.0 - self.smoothing) * magnitude_db
        )

    def get_band_peak(self, freq_hz: float, bandwidth_hz: float = 50.0) -> float:
        """Return peak dB within a narrow band around freq_hz."""
        lo = freq_hz - bandwidth_hz / 2
        hi = freq_hz + bandwidth_hz / 2
        mask = (self.frequencies >= lo) & (self.frequencies <= hi)
        if not np.any(mask):
            return -96.0
        return float(np.max(self._smoothed_magnitude_db[mask]))

    @property
    def n_bins(self):
        return len(self.frequencies)
