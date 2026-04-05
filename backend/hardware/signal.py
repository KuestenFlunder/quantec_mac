"""Signal quality monitoring for the FTDI noise diode.

Ported from Hardware.decompiled.cs: BitBangDevice.CheckSignalQuality()
"""

# Dropout threshold: quality below 0.2% means no valid signal
DROPOUT_THRESHOLD = 0.002


def check_signal_quality(zeros: int, ones: int) -> float:
    """Calculate signal quality from zero/one distribution.

    Perfect noise = 50:50 ratio = quality 1.0.
    Returns 0.0..1.0 where 1.0 is ideal.
    """
    total = zeros + ones
    if total == 0:
        return 0.0
    diff = abs(zeros - ones)
    return 1.0 - diff / total


def is_dropout(quality: float) -> bool:
    """Check if the signal quality indicates a dropout (diode disconnected)."""
    return quality < DROPOUT_THRESHOLD
