"""Configuration for :class:`~xtr_clock.bundle.clock_bundle.ClockBundle`."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_clock.timezone import resolve_timezone

__all__ = ["ClockConfig"]


@dataclass(frozen=True, slots=True)
class ClockConfig:
    """How the clock bundle builds its :class:`~xtr_clock.clock.Clock`.

    Attributes:
        timezone: The zone :meth:`~xtr_clock.clock.Clock.now` reports in.
            ``None`` follows the machine's own zone.
    """

    timezone: str | None = None

    def __post_init__(self) -> None:
        """Resolve the zone now, so a typo fails the build and not the first reading.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no zone this
                system knows.
        """
        if self.timezone is not None:
            _ = resolve_timezone(self.timezone)
