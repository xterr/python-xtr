"""Configuration for :class:`~xtr_clock.bundle.clock_bundle.ClockBundle`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from xtr_clock.timezone import resolve_timezone

__all__ = ["ClockConfig"]

#: The zone the bundle's clock reports in unless told otherwise.
_UTC: Final = "UTC"


@dataclass(frozen=True, slots=True)
class ClockConfig:
    """How the clock bundle builds its :class:`~xtr_clock.clock.Clock`.

    The clock reports in UTC unless told otherwise, so an application reads the
    same instant the same way on a laptop, in a container and in CI, whatever
    each machine's own zone is set to.

    Attributes:
        timezone: The zone :meth:`~xtr_clock.clock.Clock.now` reports in:
            ``"UTC"`` unless set, any zone name the system knows, or ``None``
            to follow the machine's own zone.
    """

    timezone: str | None = _UTC

    def __post_init__(self) -> None:
        """Resolve the zone now, so a typo fails the build and not the first reading.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no zone this
                system knows.
        """
        if self.timezone is not None:
            _ = resolve_timezone(self.timezone)
