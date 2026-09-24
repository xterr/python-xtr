"""``now()`` — the one-call front door."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .clock import Clock
from .date_point import DatePoint

if TYPE_CHECKING:
    from datetime import tzinfo

__all__ = ["now"]


def now(modifier: str = "now", timezone: str | tzinfo | None = None) -> DatePoint:
    """Return the current instant, or one described relative to it.

    The clock in force is what answers, so a test that freezes time reaches
    every call site of this function without any of them being changed.

    ```python
    now()  # right now
    now("+1 hour")  # an hour from now
    now("tomorrow")  # midnight tonight
    now("2024-04-09")  # that day, at midnight, in the clock's zone
    now("Europe/Paris")  # right now, read in Paris
    ```

    Args:
        modifier: A modifier the grammar on :mod:`xtr_clock.modifier` can
            read. Defaults to the current instant, unmodified.
        timezone: A zone to read the instant in before applying ``modifier``.

    Returns:
        The instant described.

    Raises:
        InvalidModifierError: When the grammar cannot read ``modifier``.
        InvalidTimezoneError: When ``timezone`` names no known zone.
    """
    if modifier == "now" and timezone is None:
        return Clock.get().now()

    return DatePoint.parse(modifier, timezone)
