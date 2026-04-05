"""Mock device for development without FTDI hardware.

Generates pseudo-random noise bits with ~50:50 distribution
and simulates signal quality around 0.95.
Same interface as BitBangDevice.
"""

from __future__ import annotations

import os
import threading

from .ftdi import DEFAULT_AVERAGE


class MockDevice:
    """Mock FTDI device that generates random noise for development."""

    def __init__(self):
        self._is_open = False
        self._reading = False
        self._lock = threading.Lock()
        self._signal_quality = 0.95

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def signal_quality(self) -> float:
        return self._signal_quality

    def open(self) -> bool:
        with self._lock:
            self._is_open = True
            return True

    def close(self) -> None:
        with self._lock:
            self._is_open = False
            self._reading = False

    def begin_read(self, quality: bool = True) -> bool:
        with self._lock:
            if not self._is_open:
                return False
            self._reading = True
            # Simulate signal quality warm-up
            if quality:
                self._signal_quality = 0.92 + (os.urandom(1)[0] / 255.0) * 0.08
            return True

    def end_read(self, quality: bool = True) -> None:
        with self._lock:
            self._reading = False

    def read_bits(self, count: int, average: int = DEFAULT_AVERAGE) -> bytes | None:
        """Generate random bits with ~50:50 distribution."""
        if count <= 0:
            return b""
        with self._lock:
            if not self._reading:
                return None
        # Use os.urandom for unbiased random bytes, extract LSB for each bit
        raw = os.urandom(count)
        return bytes(b & 1 for b in raw)

    def read_bytes(self, count: int) -> bytes | None:
        """Generate random bytes."""
        if count <= 0:
            return b""
        with self._lock:
            if not self._reading:
                return None
        return os.urandom(count)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()
