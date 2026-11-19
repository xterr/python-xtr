from __future__ import annotations

import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from xtr_clock import DatePoint, InvalidTimezoneError, MonotonicClock, local_timezone

PARIS = ZoneInfo("Europe/Paris")


def test_it_reports_in_the_machines_zone_by_default() -> None:
    assert MonotonicClock().timezone == local_timezone()


def test_it_reports_in_a_named_zone() -> None:
    assert MonotonicClock("Europe/Paris").timezone == PARIS


def test_it_accepts_an_already_resolved_zone() -> None:
    assert MonotonicClock(PARIS).timezone is PARIS


def test_it_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = MonotonicClock("Nope/Nope")


def test_now_answers_with_a_date_point() -> None:
    assert type(MonotonicClock("UTC").now()) is DatePoint


def test_now_answers_in_the_zone_it_was_built_with() -> None:
    assert MonotonicClock("Europe/Paris").now().tzinfo == PARIS


def test_it_starts_out_agreeing_with_the_wall_clock() -> None:
    before = datetime.now(UTC)
    moment = MonotonicClock("UTC").now()
    after = datetime.now(UTC)

    # The reading is truncated to the microsecond, so allow for that alone.
    assert (before - moment).total_seconds() < 0.001
    assert moment <= after


def test_now_only_ever_moves_forward() -> None:
    clock = MonotonicClock("UTC")

    readings = [clock.now() for _ in range(50)]

    assert readings == sorted(readings)


def test_sleep_lets_real_time_pass() -> None:
    clock = MonotonicClock("UTC")

    before = clock.now()
    clock.sleep(0.05)

    assert (clock.now() - before).total_seconds() >= 0.05


@pytest.mark.parametrize("seconds", [0, -1, -0.5])
def test_sleep_returns_at_once_for_nothing_or_less(seconds: float) -> None:
    started = time.monotonic()

    MonotonicClock("UTC").sleep(seconds)

    assert time.monotonic() - started < 0.05


@pytest.mark.anyio
async def test_sleep_async_lets_real_time_pass() -> None:
    clock = MonotonicClock("UTC")

    before = clock.now()
    await clock.sleep_async(0.05)

    assert (clock.now() - before).total_seconds() >= 0.05


def test_with_timezone_leaves_the_original_alone() -> None:
    clock = MonotonicClock("UTC")

    moved = clock.with_timezone("Europe/Paris")

    assert moved is not clock
    assert clock.timezone != PARIS
    assert moved.timezone == PARIS


def test_with_timezone_keeps_the_anchor_so_the_two_clocks_agree() -> None:
    clock = MonotonicClock("UTC")

    moved = clock.with_timezone("Europe/Paris")

    assert abs((moved.now() - clock.now()).total_seconds()) < 0.05


def test_with_timezone_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = MonotonicClock("UTC").with_timezone("Nope/Nope")


def test_it_reads_as_the_zone_it_reports_in() -> None:
    assert repr(MonotonicClock("Europe/Paris")) == "MonotonicClock(Europe/Paris)"
