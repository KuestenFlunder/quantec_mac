"""FTDI D2XX BitBang device wrapper using pyftdi.

Ported 1:1 from Hardware.decompiled.cs: BitBangDevice (lines 32-412).
Communicates with an FT232R in AsyncBitBang mode to read noise bits
from a hardware diode connected to RXD (pin D1).
"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

from pyftdi.ftdi import Ftdi

from .signal import check_signal_quality, is_dropout

logger = logging.getLogger(__name__)

# --- Constants (from C# source) ---
BAUD_RATE = 57600
PIN_MASK_ON = 0x34       # D2+D4+D5 output; BitBang read mode
PIN_MASK_OFF = 0x37      # D0+D1+D2+D4+D5 output; idle mode
CMD_DIODE_ON = bytes([0x10])   # DTR HIGH -> diode power on
CMD_DIODE_OFF = bytes([0x14])  # DTR+RTS HIGH -> diode power off
NOISE_BIT_MASK = 0x02    # Bit 1 = RXD = noise signal
DEFAULT_AVERAGE = 11     # Raw samples per output bit
BUFFER_SIZE = 32768      # Internal buffer size (matches C# bitBuffer)
READ_TIMEOUT_MS = 5000


class DeviceInterface(Protocol):
    """Protocol that both real and mock devices implement."""

    def open(self) -> bool: ...
    def close(self) -> None: ...
    def begin_read(self, quality: bool = True) -> bool: ...
    def end_read(self, quality: bool = True) -> None: ...
    def read_bits(self, count: int, average: int = DEFAULT_AVERAGE) -> bytes | None: ...
    def read_bytes(self, count: int) -> bytes | None: ...

    @property
    def signal_quality(self) -> float: ...

    @property
    def is_open(self) -> bool: ...


class BitBangDevice:
    """FTDI FT232R BitBang device for reading hardware noise bits.

    Direct port of the C# BitBangDevice class.
    """

    def __init__(self, url: str | None = None):
        self._url = url or "ftdi://ftdi:232/1"
        self._ftdi: Ftdi | None = None
        self._lock = threading.Lock()
        self._zeros: int = 0
        self._ones: int = 0
        self._signal_quality: float = 0.0
        self._signal_dropout: bool = False

    @property
    def is_open(self) -> bool:
        return self._ftdi is not None and self._ftdi.is_connected

    @property
    def signal_quality(self) -> float:
        return min(max(0.0, self._signal_quality), 1.0)

    def open(self) -> bool:
        """Open device: FT_OpenEx -> FT_ResetPort -> FT_SetBaudRate(57600)."""
        with self._lock:
            if self.is_open:
                return True
            try:
                self._ftdi = Ftdi()
                self._ftdi.open_from_url(self._url)
                self._ftdi.reset(usb_dev=False)
                self._ftdi.set_baudrate(BAUD_RATE)
                return True
            except Exception:
                logger.exception("Failed to open FTDI device at %s", self._url)
                self._ftdi = None
                return False

    def close(self) -> None:
        """Close the device and reset BitMode."""
        if self.is_open:
            try:
                self._ftdi.set_bitmode(0x00, Ftdi.BitMode.RESET)
            except Exception:
                pass
            try:
                self._ftdi.close()
            except Exception:
                pass
        self._ftdi = None

    def begin_read(self, quality: bool = True) -> bool:
        """Start noise reading session.

        1. Set BitMode to AsyncBitBang with PIN_MASK_ON
        2. Write CMD_DIODE_ON
        3. Purge receive buffer
        4. Optionally run signal quality check (up to 42 rounds)
        """
        with self._lock:
            if not self.is_open:
                return False
            try:
                self._ftdi.set_bitmode(PIN_MASK_ON, Ftdi.BitMode.BITBANG)
                written = self._ftdi.write_data(CMD_DIODE_ON)
                if written != len(CMD_DIODE_ON):
                    return False
                self._ftdi.purge_rx_buffer()

                self._zeros = 0
                self._ones = 0
                self._signal_dropout = False

                low_threshold = max(0.4, self._signal_quality - 0.2)
                high_threshold = max(0.8, self._signal_quality)

                if quality:
                    for i in range(1, 43):  # 1..42 inclusive
                        raw = self._ftdi.read_data(BUFFER_SIZE)
                        if len(raw) != BUFFER_SIZE:
                            return False

                        for b in raw:
                            if b & NOISE_BIT_MASK:
                                self._ones += 1
                            else:
                                self._zeros += 1

                        ok = self._check_signal_quality()

                        if self._signal_quality > high_threshold and ok:
                            return True
                        if i > 14 and self._signal_quality > low_threshold and ok:
                            return True
                        if i > 28 and ok:
                            return True
                    return False

                return True
            except Exception:
                logger.exception("begin_read failed")
                return False

    def end_read(self, quality: bool = True) -> None:
        """Stop noise reading: set PIN_MASK_OFF and write CMD_DIODE_OFF."""
        with self._lock:
            if not self.is_open:
                return
            try:
                self._ftdi.set_bitmode(PIN_MASK_OFF, Ftdi.BitMode.BITBANG)
                self._ftdi.write_data(CMD_DIODE_OFF)
            except Exception:
                logger.exception("end_read failed")

    def read_bits(self, count: int, average: int = DEFAULT_AVERAGE) -> bytes | None:
        """Read noise bits with averaging.

        For each output bit, reads `average * 11` raw bytes from the FTDI chip,
        extracts bit 1 (RXD), and applies majority vote.

        Returns a bytes object of length `count` where each byte is 0 or 1,
        or None on failure.
        """
        if count <= 0:
            return b""

        with self._lock:
            if not self.is_open:
                return None

            samples_per_bit = 11 * average if average >= 1 else 11
            result = bytearray(count)
            offset = 0

            try:
                while offset < count:
                    remaining = count - offset
                    chunk = min(remaining * samples_per_bit, BUFFER_SIZE)
                    chunk -= chunk % samples_per_bit  # align

                    self._ftdi.set_latency_timer(16)
                    raw = self._ftdi.read_data(chunk)
                    if not raw or len(raw) == 0 or len(raw) > chunk:
                        return None

                    # Extract noise bits and count zeros/ones
                    bits = bytearray(len(raw))
                    for i, b in enumerate(raw):
                        is_one = (b & NOISE_BIT_MASK) != 0
                        if is_one:
                            self._ones += 1
                        else:
                            self._zeros += 1
                        bits[i] = 1 if is_one else 0

                    # Signal quality check
                    if not self._check_signal_quality():
                        if self._signal_dropout:
                            return None
                        self._signal_dropout = True
                        logger.warning("Signal dropout -- cycling diode")
                        self._ftdi.write_data(CMD_DIODE_OFF)
                        self._ftdi.write_data(CMD_DIODE_ON)
                        # Discard 14 rounds of garbage
                        for _ in range(14):
                            self._ftdi.read_data(BUFFER_SIZE)
                        continue  # retry this chunk

                    # Averaging: majority vote per samples_per_bit
                    pos = 0
                    spb = samples_per_bit
                    for j in range(len(raw)):
                        pos += bits[j]
                        if (j + 1) % spb == 0:
                            idx = j // spb
                            result[offset + idx] = 1 if (pos * 2 > spb) else 0
                            pos = 0

                    produced = len(raw) // spb
                    offset += produced

                return bytes(result)
            except Exception:
                logger.exception("read_bits failed")
                return None

    def read_bytes(self, count: int) -> bytes | None:
        """Read random bytes by assembling 8 bits per byte.

        Each byte is constructed MSB-first from 8 noise bits (average=1).
        """
        if count <= 0:
            return b""

        total_bits = count * 8
        raw_bits = self.read_bits(total_bits, average=1)
        if raw_bits is None:
            return None

        result = bytearray(count)
        for byte_idx in range(count):
            val = 0
            mask = 128  # MSB first
            for bit_offset in range(8):
                if raw_bits[byte_idx * 8 + bit_offset]:
                    val |= mask
                mask >>= 1
            result[byte_idx] = val

        return bytes(result)

    def _check_signal_quality(self) -> bool:
        """Update signal quality from accumulated zero/one counts.

        Uses exponential moving average: q = 0.9*old + 0.1*new.
        Returns False if quality drops below 0.2% (dropout).
        """
        if self._zeros + self._ones < BUFFER_SIZE:
            return True

        q = check_signal_quality(self._zeros, self._ones)
        self._zeros = 0
        self._ones = 0

        if is_dropout(q):
            self._signal_quality = 0.0
            logger.warning("Signal quality %.1f%% -- dropout", q * 100)
            return False

        self._signal_quality = 0.9 * self._signal_quality + 0.1 * q
        logger.debug("Signal quality %.1f%%", self.signal_quality * 100)
        return True

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        self.close()
