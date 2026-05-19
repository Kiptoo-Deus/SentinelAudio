"""
Audio capture engine using sounddevice.
Streams audio from the selected input device into a ring buffer
consumed by the FFT engine on a separate thread.
"""

import threading
import numpy as np
import sounddevice as sd
from collections import deque


class AudioCapture:
    def __init__(self, device_index=None, sample_rate=48000, buffer_size=1024, channels=1):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.channels = channels

        self._ring_buffer = deque(maxlen=8)
        self._lock = threading.Lock()
        self._stream = None
        self._running = False
        self._level_db = -96.0

        self.on_buffer = None  # callback: fn(np.ndarray)

    def get_available_devices(self):
        devices = []
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                devices.append({
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": int(dev["default_samplerate"]),
                })
        return devices

    def start(self):
        if self._running:
            return

        kwargs = dict(
            samplerate=self.sample_rate,
            blocksize=self.buffer_size,
            channels=self.channels,
            dtype="float32",
            callback=self._audio_callback,
        )
        if self.device_index is not None:
            kwargs["device"] = self.device_index

        self._stream = sd.InputStream(**kwargs)
        self._stream.start()
        self._running = True

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._running = False

    def _audio_callback(self, indata, frames, time_info, status):
        mono = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()

        rms = np.sqrt(np.mean(mono ** 2))
        self._level_db = 20 * np.log10(rms + 1e-10)

        with self._lock:
            self._ring_buffer.append(mono)

        if self.on_buffer:
            self.on_buffer(mono)

    def get_level_db(self):
        return self._level_db

    @property
    def is_running(self):
        return self._running
