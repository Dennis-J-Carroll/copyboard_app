"""Chamber numbering and capacity rules shared by every CopyBoard surface.

This is the *only* place that converts between the zero-based list indexes
used by :mod:`copyboard_extension.core` and the one-based chamber numbers
(``01`` – ``16``) that people see.  The editor, the compact widget, the
global hotkeys, and the tests all import these helpers instead of doing
``index + 1`` arithmetic on their own.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

MIN_CHAMBERS = 10
MAX_CHAMBERS = 16
DEFAULT_CHAMBERS = 10


def normalize_chamber_count(value: object, default: int = DEFAULT_CHAMBERS) -> int:
    """Coerce any configured value into the supported 10–16 range.

    Numeric strings and floats are accepted so legacy ``config.json`` files
    keep working.  Values outside the range are clamped rather than rejected:
    a user who once configured a 42-item generic history gets the largest
    cylinder we support, and a user with ``5`` gets the smallest.  Anything
    that is not a number falls back to ``default``.
    """
    if isinstance(value, bool):
        return default
    try:
        count = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(MIN_CHAMBERS, min(MAX_CHAMBERS, count))


def is_valid_chamber_count(value: object) -> bool:
    """Return True only for an integer already inside the supported range."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and MIN_CHAMBERS <= value <= MAX_CHAMBERS
    )


def chamber_number(index: int) -> int:
    """Zero-based board index -> one-based chamber number (0 -> 1)."""
    return int(index) + 1


def chamber_index(number: int) -> int:
    """One-based chamber number -> zero-based board index (1 -> 0)."""
    return int(number) - 1


def chamber_label(index: int) -> str:
    """Zero-based board index -> the two-digit label shown in the UI."""
    return f"{chamber_number(index):02d}"


def is_chamber_index(index: object, count: int) -> bool:
    """True when ``index`` addresses one of ``count`` chambers."""
    return (
        isinstance(index, int)
        and not isinstance(index, bool)
        and 0 <= index < count
    )


class ChamberDial:
    """Turn typed digits into a chamber selection without modifier keys.

    ``1``–``9`` select chambers 01–09 immediately and ``0`` selects chamber
    10.  If a second digit arrives within ``window`` seconds the two digits
    are combined, so ``1`` then ``2`` selects chamber 12 and ``1`` then ``6``
    selects chamber 16.  Combinations beyond the configured count are
    ignored, so the dial is safe on a ten-chamber cylinder.
    """

    def __init__(
        self,
        count_provider: Callable[[], int],
        window: float = 0.65,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._count_provider = count_provider
        self._window = window
        self._clock = clock
        self._pending_digit: Optional[int] = None
        self._pending_at = 0.0

    def press(self, digit: str) -> Optional[int]:
        """Feed one typed digit; return the selected zero-based index or None."""
        if not digit.isdigit() or len(digit) != 1:
            return None
        count = self._count_provider()
        value = int(digit)
        now = self._clock()

        if (
            self._pending_digit is not None
            and now - self._pending_at <= self._window
        ):
            combined = self._pending_digit * 10 + value
            self._pending_digit = None
            if 1 <= combined <= count:
                return chamber_index(combined)
            # Fall through and treat the new digit on its own.

        self._pending_digit = value if value != 0 else None
        self._pending_at = now
        number = 10 if value == 0 else value
        if number <= count:
            return chamber_index(number)
        return None

    def reset(self) -> None:
        self._pending_digit = None
