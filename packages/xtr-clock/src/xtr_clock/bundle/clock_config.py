"""Configuration for :class:`~xtr_clock.bundle.clock_bundle.ClockBundle`."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ClockConfig"]


@dataclass(frozen=True, slots=True)
class ClockConfig:
    """How the clock bundle builds its :class:`~xtr_clock.clock.Clock`.

    Attributes:
        timezone: The zone :meth:`~xtr_clock.clock.Clock.now` reports in.
            ``None`` follows the wrapped clock — the machine's own zone in
            production, and UTC for a frozen mock.
        mock: When ``True``, the bundle wraps a
            :class:`~xtr_clock.mock_clock.MockClock` instead of a
            :class:`~xtr_clock.system_clock.SystemClock`, so a test-shaped
            application freezes time by configuration alone.
        frozen_at: Where the mock clock stands still. Read by the grammar on
            :mod:`xtr_clock.modifier` — an absolute datetime, a keyword, or
            ``None`` to freeze at the current instant.

    Raises:
        ValueError: When ``frozen_at`` is given without ``mock=True``, since
            it means nothing to freeze a wall clock.
    """

    timezone: str | None = None
    mock: bool = False
    frozen_at: str | None = None

    def __post_init__(self) -> None:
        """Refuse a ``frozen_at`` unless ``mock`` is enabled."""
        if self.frozen_at is not None and not self.mock:
            message = "frozen_at requires mock=True"
            raise ValueError(message)
