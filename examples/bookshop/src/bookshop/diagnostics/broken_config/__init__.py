"""A kernel whose configuration conflicts: two unconditional base providers for one config."""

from __future__ import annotations

from xtr_clock.bundle import ClockConfig
from xtr_dependency_injection import configure

__all__ = ["clock_in_paris", "clock_in_utc"]


@configure
def clock_in_utc() -> ClockConfig:
    """Provide one base config."""
    return ClockConfig(timezone="UTC")


@configure
def clock_in_paris() -> ClockConfig:
    """Provide another, equally unconditional: ``ConflictingConfigProvidersError`` names both."""
    return ClockConfig(timezone="Europe/Paris")
