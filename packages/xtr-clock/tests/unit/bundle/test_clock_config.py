"""Unit tests for :class:`xtr_clock.bundle.ClockConfig`."""

from __future__ import annotations

import pytest

from xtr_clock import InvalidTimezoneError
from xtr_clock.bundle import ClockConfig


def test_no_timezone_follows_the_machines_own_zone() -> None:
    assert ClockConfig().timezone is None


def test_a_known_zone_is_kept_as_it_was_written() -> None:
    assert ClockConfig(timezone="Europe/Paris").timezone == "Europe/Paris"


def test_a_zone_this_system_does_not_know_is_refused_where_it_is_written() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = ClockConfig(timezone="Not/AZone")
