"""The application's clock configuration: a mock frozen at a known instant."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_clock.bundle import ClockConfig


@configure
def clock() -> ClockConfig:
    """Freeze the clock at a known instant for the whole integration test."""
    return ClockConfig(mock=True, frozen_at="2026-01-01 00:00:00")
