"""Diode scan algorithms -- ported 1:1 from Hardware.decompiled.cs.

Classes:
  BasicDiode       (lines 808-919)  -- base with recover/send
  SelectionDiode   (lines 1237-1305) -- standard scan with normalization
  QUANTEC6Diode    (lines 1028-1129) -- bit extraction with cumulative walk
  QUANTEC6DiodeWithRandom (lines 1130-1236) -- hardware + software random
  DistributionDiode (lines 920-967) -- uint32 cumulative distribution
  RemainderDiode   (lines 968-1027) -- XOR uint64 power iteration
"""

from __future__ import annotations

import enum
import logging
import math
import random
import struct
import threading
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .ftdi import DeviceInterface

logger = logging.getLogger(__name__)

BUFFER_SIZE = 4096


class DiodeOperation(enum.Enum):
    SINGLE_SCAN = 0
    FIRST_SCAN = 1
    IN_BETWEEN_SCAN = 2
    LAST_SCAN = 3
    SEND = 4
    RECOVER = 5


class DiodeState(enum.Enum):
    ERROR = -1
    IDLE = 0
    SCANNING = 1
    SENDING = 2


class DiodeType(enum.Enum):
    QUANTEC6 = 0
    QUANTEC6_WITH_RANDOM = 1
    REMAINDER = 2
    DISTRIBUTION = 3
    SELECTION = 4
    DEFAULT = 1


# Callback type for state change notifications
DiodeStateHandler = Callable[[DiodeState], None]


class BinaryBuffer:
    """Simple binary buffer with sequential read pointer (mirrors C# BinaryBuffer)."""

    def __init__(self, size: int):
        self._data = bytearray(size)
        self._index = 0

    @property
    def buffer(self) -> bytearray:
        return self._data

    @property
    def length(self) -> int:
        return len(self._data)

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        self._index = value

    def read_uint8(self) -> int:
        val = self._data[self._index]
        self._index += 1
        return val

    def read_uint32(self) -> int:
        val = struct.unpack_from("<I", self._data, self._index)[0]
        self._index += 4
        return val

    def read_uint64(self) -> int:
        val = struct.unpack_from("<Q", self._data, self._index)[0]
        self._index += 8
        return val


class BasicDiode:
    """Base diode class with recover() and send() operations.

    Ported from Hardware.decompiled.cs lines 808-919.
    """

    _buffer = BinaryBuffer(BUFFER_SIZE)
    _device: DeviceInterface | None = None
    _retries: int = 0
    _state_handler: DiodeStateHandler | None = None
    _lock = threading.Lock()

    def __init__(self, device: DeviceInterface | None = None):
        if device is not None:
            BasicDiode._device = device

    @classmethod
    def set_state_handler(cls, handler: DiodeStateHandler | None) -> None:
        cls._state_handler = handler

    @classmethod
    def _on_state_changed(cls, state: DiodeState) -> None:
        if cls._state_handler:
            try:
                cls._state_handler(state)
            except Exception:
                logger.exception("State handler error")

    @property
    def device(self) -> DeviceInterface | None:
        dev = BasicDiode._device
        if dev is not None:
            BasicDiode._retries = 0
        else:
            BasicDiode._retries += 1
        if dev is not None and dev.is_open:
            return dev
        if dev is not None:
            if dev.open():
                return dev
        self._end(DiodeOperation.RECOVER, DiodeState.ERROR, success=False)
        return None

    def recover(self) -> bool:
        """Test-read one byte to check if device is working."""
        with BasicDiode._lock:
            dev = self.device
            if dev is None:
                return False
            if not self._begin(DiodeOperation.RECOVER, DiodeState.IDLE):
                return self._end(DiodeOperation.RECOVER, DiodeState.ERROR, success=False)
            result = dev.read_bytes(1)
            if result is None:
                return self._end(DiodeOperation.RECOVER, DiodeState.ERROR, success=False)
            return self._end(DiodeOperation.RECOVER, DiodeState.IDLE, success=True)

    def send(self, duration: float, cancel: Callable[[], bool] | None = None) -> bool:
        """Read noise bytes for `duration` seconds (the 'send' operation).

        The original C# code reads bytes continuously for the duration.
        No data is written to the diode -- reading IS the sending.
        """
        if duration < 0:
            raise ValueError("duration must be non-negative")

        with BasicDiode._lock:
            dev = self.device
            if dev is None:
                return False
            if not self._begin(DiodeOperation.SEND, DiodeState.SENDING):
                return self._end(DiodeOperation.SEND, DiodeState.ERROR, success=False)
            # Initial test read
            if dev.read_bytes(1) is None:
                return self._end(DiodeOperation.SEND, DiodeState.ERROR, success=False)

            end_time = time.monotonic() + duration
            read_size = BasicDiode._buffer.length // 4  # 1024 bytes per iteration

            while time.monotonic() < end_time:
                if cancel and cancel():
                    return self._end(DiodeOperation.SEND, DiodeState.IDLE, success=False)
                if dev.read_bytes(read_size) is None:
                    return self._end(DiodeOperation.SEND, DiodeState.ERROR, success=False)

            return self._end(DiodeOperation.SEND, DiodeState.IDLE, success=True)

    def scan(
        self,
        operation: DiodeOperation,
        data: list[int],
        cycles: int,
        cancel: Callable[[], bool] | None = None,
    ) -> bool:
        """Override in subclasses."""
        raise NotImplementedError

    def _begin(self, operation: DiodeOperation, state: DiodeState) -> bool:
        """Start a diode operation: BeginRead with quality check for certain ops."""
        dev = BasicDiode._device
        if dev is None:
            return False
        needs_quality = operation in (
            DiodeOperation.FIRST_SCAN,
            DiodeOperation.SINGLE_SCAN,
            DiodeOperation.RECOVER,
            DiodeOperation.SEND,
        )
        result = dev.begin_read(quality=needs_quality)
        if operation != DiodeOperation.RECOVER:
            self._on_state_changed(state)
        return result

    def _end(self, operation: DiodeOperation, state: DiodeState, success: bool) -> bool:
        """End a diode operation."""
        dev = BasicDiode._device
        if state == DiodeState.ERROR:
            if dev is not None:
                dev.close()
            BasicDiode._device = None
        else:
            if dev is not None:
                needs_quality = operation in (
                    DiodeOperation.LAST_SCAN,
                    DiodeOperation.SINGLE_SCAN,
                    DiodeOperation.RECOVER,
                )
                dev.end_read(quality=needs_quality)
        self._on_state_changed(state)
        return success


class SelectionDiode(BasicDiode):
    """Standard scan: sequential walk with bit normalization.

    Ported from Hardware.decompiled.cs lines 1237-1305.

    Algorithm:
    1. average = 1 + log2(N)
    2. For each of N*cycles iterations:
       - Read 1 noise bit (with averaging)
       - Walk sequentially through data[] slots
       - If bit=1: data[pos]++
    3. Normalize: data[j] /= (ones / (ones + zeros))
    """

    def scan(
        self,
        operation: DiodeOperation,
        data: list[int],
        cycles: int,
        cancel: Callable[[], bool] | None = None,
    ) -> bool:
        if data is None:
            raise ValueError("data must not be None")
        if cycles < 0:
            raise ValueError("cycles must be non-negative")

        with BasicDiode._lock:
            dev = self.device
            if dev is None:
                return False

            self._begin(operation, DiodeState.SCANNING)
            n = len(data)
            for i in range(n):
                data[i] = 0

            average = 1 + int(math.log2(n)) if n > 1 else 1
            total = n * cycles
            pos = 0
            ones = 0.0
            zeros = 0.0

            while total > 0:
                if cancel and cancel():
                    return self._end(operation, DiodeState.IDLE, success=False)

                chunk_size = min(total, BasicDiode._buffer.length)
                bits = dev.read_bits(chunk_size, average=average)
                if bits is None:
                    return self._end(operation, DiodeState.ERROR, success=False)

                for i in range(len(bits)):
                    if pos >= n:
                        pos = 0
                    if bits[i] != 0:
                        data[pos] += 1
                        ones += 1.0
                    else:
                        zeros += 1.0
                    pos += 1

                total -= len(bits)

            result = self._end(operation, DiodeState.IDLE, success=True)

            # Normalization: correct for actual 0/1 bias
            if ones > 0:
                ratio = ones / (zeros + ones)
                for j in range(n):
                    data[j] = int(data[j] / ratio)

            return result


class QUANTEC6Diode(BasicDiode):
    """Bit extraction with cumulative walk.

    Ported from Hardware.decompiled.cs lines 1028-1129.

    Algorithm:
    1. bits_needed = ceil(log2(N))
    2. bytes_per_selection = ceil(bits_needed / 8)
    3. For each of N*cycles iterations:
       - Extract bits_needed bits from byte stream
       - Add previous index (cumulative walk)
       - Add 1
       - Modulo N
       - data[index]++
    """

    def scan(
        self,
        operation: DiodeOperation,
        data: list[int],
        cycles: int,
        cancel: Callable[[], bool] | None = None,
    ) -> bool:
        if data is None:
            raise ValueError("data must not be None")
        if cycles < 0:
            raise ValueError("cycles must be non-negative")

        with BasicDiode._lock:
            dev = self.device
            if dev is None:
                return False

            self._begin(operation, DiodeState.SCANNING)
            n = len(data)
            for i in range(n):
                data[i] = 0

            # Calculate bits needed per selection
            bits_needed = 1
            while bits_needed < 32 and (1 << bits_needed) < n:
                bits_needed += 1

            bytes_per_sel = (bits_needed + 7) // 8
            remaining = n * cycles

            # Bit-stream state
            current_byte = 0
            bits_left = 0
            first_read = True
            prev_index = 0

            while remaining > 0:
                if cancel and cancel():
                    return self._end(operation, DiodeState.IDLE, success=False)

                read_size = min(remaining * bytes_per_sel, BasicDiode._buffer.length)
                raw = dev.read_bytes(read_size)
                if raw is None:
                    return self._end(operation, DiodeState.ERROR, success=False)

                # Copy into buffer for sequential reading
                buf = BasicDiode._buffer
                buf.buffer[:len(raw)] = raw
                buf.index = 0

                if first_read:
                    current_byte = buf.read_uint8()
                    bits_left = 8
                    first_read = False

                while read_size - buf.index >= bytes_per_sel:
                    # Extract bits_needed bits from the stream
                    value = 0
                    need = bits_needed

                    if need > 0:
                        take = min(need, bits_left)
                        value = current_byte
                        if take < 8:
                            value >>= (bits_left - take)
                            value &= (1 << take) - 1
                        need -= take
                        bits_left -= take

                    if bits_left <= 0:
                        current_byte = buf.read_uint8()
                        bits_left = 8

                    while need >= 8:
                        value <<= 8
                        value |= current_byte
                        need -= 8
                        current_byte = buf.read_uint8()
                        bits_left = 8

                    if need > 0:
                        value <<= need
                        value |= (current_byte >> (8 - need))
                        bits_left -= need

                    # Cumulative walk
                    value += prev_index
                    value += 1
                    value %= n

                    if 0 <= value < n:
                        data[value] += 1
                    prev_index = value

                    remaining -= 1
                    if remaining == 0:
                        break

            return self._end(operation, DiodeState.IDLE, success=True)


class QUANTEC6DiodeWithRandom(BasicDiode):
    """Hardware + software random scan.

    Ported from Hardware.decompiled.cs lines 1130-1236.

    Like QUANTEC6Diode but adds random.randint() to the extracted bits.
    No cumulative walk (no carry-over of previous index).
    """

    def scan(
        self,
        operation: DiodeOperation,
        data: list[int],
        cycles: int,
        cancel: Callable[[], bool] | None = None,
    ) -> bool:
        if data is None:
            raise ValueError("data must not be None")
        if cycles < 0:
            raise ValueError("cycles must be non-negative")

        with BasicDiode._lock:
            dev = self.device
            if dev is None:
                return False

            self._begin(operation, DiodeState.SCANNING)
            n = len(data)
            for i in range(n):
                data[i] = 0

            bits_needed = 1
            while bits_needed < 32 and (1 << bits_needed) < n:
                bits_needed += 1

            bytes_per_sel = (bits_needed + 7) // 8
            remaining = n * cycles

            current_byte = 0
            bits_left = 0
            first_read = True
            rng = random.Random()

            while remaining > 0:
                if cancel and cancel():
                    return self._end(operation, DiodeState.IDLE, success=False)

                read_size = min(remaining * bytes_per_sel, BasicDiode._buffer.length)
                raw = dev.read_bytes(read_size)
                if raw is None:
                    return self._end(operation, DiodeState.ERROR, success=False)

                buf = BasicDiode._buffer
                buf.buffer[:len(raw)] = raw
                buf.index = 0

                if first_read:
                    current_byte = buf.read_uint8()
                    bits_left = 8
                    first_read = False

                while read_size - buf.index >= bytes_per_sel:
                    value = 0
                    need = bits_needed

                    if need > 0:
                        take = min(need, bits_left)
                        value = current_byte
                        if take < 8:
                            value >>= (bits_left - take)
                            value &= (1 << take) - 1
                        need -= take
                        bits_left -= take

                    if bits_left <= 0:
                        current_byte = buf.read_uint8()
                        bits_left = 8

                    while need >= 8:
                        value <<= 8
                        value |= current_byte
                        need -= 8
                        current_byte = buf.read_uint8()
                        bits_left = 8
                        remaining -= 1
                        if remaining == 0:
                            break

                    if remaining > 0:
                        if need > 0:
                            value <<= need
                            value |= (current_byte >> (8 - need))
                            bits_left -= need

                        # Add software random (matches C# random.Next())
                        value += rng.randint(0, 2**31 - 1)
                        value %= n

                        if 0 <= value < n:
                            data[value] += 1

                    remaining -= 1
                    if remaining == 0:
                        break

            return self._end(operation, DiodeState.IDLE, success=True)


class DistributionDiode(BasicDiode):
    """Distribution scan using cumulative uint32 sums.

    Ported from Hardware.decompiled.cs lines 920-967.

    Algorithm:
    1. Read N * 4 * cycles bytes
    2. For each 4-byte block: cumulative_sum += ReadUInt32()
    3. index = (cumulative_sum * N) >> 32
    4. data[index]++
    """

    def scan(
        self,
        operation: DiodeOperation,
        data: list[int],
        cycles: int,
        cancel: Callable[[], bool] | None = None,
    ) -> bool:
        if data is None:
            raise ValueError("data must not be None")
        if cycles < 0:
            raise ValueError("cycles must be non-negative")

        with BasicDiode._lock:
            dev = self.device
            if dev is None:
                return False

            self._begin(operation, DiodeState.SCANNING)
            n = len(data)
            for i in range(n):
                data[i] = 0

            total_bytes = n * 4 * cycles
            cumulative = 0

            while total_bytes > 0:
                if cancel and cancel():
                    return self._end(operation, DiodeState.IDLE, success=False)

                read_size = min(total_bytes, BasicDiode._buffer.length)
                raw = dev.read_bytes(read_size)
                if raw is None:
                    return self._end(operation, DiodeState.ERROR, success=False)

                buf = BasicDiode._buffer
                buf.buffer[:len(raw)] = raw
                buf.index = 0

                for _ in range(len(raw) // 4):
                    cumulative = (cumulative + buf.read_uint32()) & 0xFFFFFFFF
                    # (sum * N) >> 32  -- upper 32 bits of 64-bit product
                    idx = (cumulative * n) >> 32
                    if 0 <= idx < n:
                        data[idx] += 1

                total_bytes -= len(raw)

            return self._end(operation, DiodeState.IDLE, success=True)


class RemainderDiode(BasicDiode):
    """Remainder-based scan using XOR uint64 and power iteration.

    Ported from Hardware.decompiled.cs lines 968-1027.

    Algorithm:
    1. For N*cycles iterations:
       - Read uint32, XOR into upper 32 bits of uint64
       - For each power of N fitting in uint64:
         index = (cumulative / N^k) % N
         data[index]++
    """

    def scan(
        self,
        operation: DiodeOperation,
        data: list[int],
        cycles: int,
        cancel: Callable[[], bool] | None = None,
    ) -> bool:
        if data is None:
            raise ValueError("data must not be None")
        if cycles < 0:
            raise ValueError("cycles must be non-negative")

        with BasicDiode._lock:
            dev = self.device
            if dev is None:
                return False

            self._begin(operation, DiodeState.SCANNING)
            n = len(data)
            for i in range(n):
                data[i] = 0

            remaining = n * cycles

            while remaining > 0:
                if cancel and cancel():
                    return self._end(operation, DiodeState.IDLE, success=False)

                # Estimate bytes needed (matches C# formula)
                est = int(math.log(n, 2.0) / 8.0 * remaining)
                read_size = min((est | 3) + 5, BasicDiode._buffer.length)

                raw = dev.read_bytes(read_size)
                if raw is None:
                    return self._end(operation, DiodeState.ERROR, success=False)

                buf = BasicDiode._buffer
                buf.buffer[:len(raw)] = raw
                buf.index = 0

                cumulative_index = 0
                # First uint32
                val64 = buf.read_uint32()

                while buf.index + 4 <= len(raw):
                    # XOR next uint32 into upper 32 bits
                    next32 = buf.read_uint32()
                    val64 ^= next32 << 32

                    # Power iteration: extract multiple indices from uint64
                    power = 1
                    while power <= 0xFFFFFFFF:
                        cumulative_index += int(val64 // power % n)
                        data[cumulative_index % n] += 1
                        remaining -= 1
                        if remaining == 0:
                            break
                        power *= n

                    if remaining == 0:
                        break

                    # Shift: keep upper 32 bits
                    val64 >>= 32

            return self._end(operation, DiodeState.IDLE, success=True)
