"""Configuration for :class:`~xtr_clock.bundle.clock_bundle.ClockBundle`."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ClockConfig"]


@dataclass(frozen=True, slots=True)
class ClockConfig:
    """How the clock bundle builds its :class:`~xtr_clock.clock.Clock`.

    Attributes:
        timezone: The zone :meth:`~xtr_clock.clock.Clock.now` reports in.
            ``None`` follows the machine's own zone.
    """

    timezone: str | None = None
