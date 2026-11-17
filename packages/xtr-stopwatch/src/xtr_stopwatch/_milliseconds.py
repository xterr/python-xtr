"""The one reading every timing in this library is taken with."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from xtr_clock import ClockInterface

__all__ = ["now_ms"]

_MILLISECONDS_PER_SECOND: Final = 1000.0


def now_ms(clock: ClockInterface) -> float:
    """Return ``clock``'s current instant, in milliseconds since the epoch."""
    return clock.now().timestamp() * _MILLISECONDS_PER_SECOND
