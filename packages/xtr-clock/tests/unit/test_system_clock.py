from __future__ import annotations

import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from xtr_clock import DatePoint, InvalidTimezoneError, SystemClock, local_timezone

PARIS = ZoneInfo("Europe/Paris")


def test_it_reports_in_the_machines_zone_by_default() -> None:
    assert SystemClock().timezone == local_timezone()


def test_it_reports_in_a_named_zone() -> None:
    assert SystemClock("Europe/Paris").timezone == PARIS


def test_it_accepts_an_already_resolved_zone() -> None:
    assert SystemClock(PARIS).timezone is PARIS


def test_it_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = SystemClock("Nope/Nope")


def test_now_answers_with_a_date_point() -> None:
    assert type(SystemClock("UTC").now()) is DatePoint


def test_now_answers_in_the_zone_it_was_built_with() -> None:
    assert SystemClock("Europe/Paris").now().tzinfo == PARIS


def test_now_sits_between_two_readings_of_the_system_clock() -> None:
    before = datetime.now(UTC)
    moment = SystemClock("UTC").now()
    after = datetime.now(UTC)

    assert before <= moment <= after


def test_now_moves_between_two_readings() -> None:
    clock = SystemClock("UTC")

    first = clock.now()
    time.sleep(0.01)
    second = clock.now()

    assert second > first


def test_sleep_lets_real_time_pass() -> None:
    clock = SystemClock("UTC")

    before = clock.now()
    clock.sleep(0.05)

    assert (clock.now() - before).total_seconds() >= 0.05


@pytest.mark.parametrize("seconds", [0, -1, -0.5])
def test_sleep_returns_at_once_for_nothing_or_less(seconds: float) -> None:
    started = time.monotonic()

    SystemClock("UTC").sleep(seconds)

    assert time.monotonic() - started < 0.05


@pytest.mark.anyio
async def test_sleep_async_lets_real_time_pass() -> None:
    clock = SystemClock("UTC")

    before = clock.now()
    await clock.sleep_async(0.05)

    assert (clock.now() - before).total_seconds() >= 0.05


@pytest.mark.anyio
@pytest.mark.parametrize("seconds", [0, -1])
async def test_sleep_async_returns_at_once_for_nothing_or_less(seconds: float) -> None:
    started = time.monotonic()

    await SystemClock("UTC").sleep_async(seconds)

    assert time.monotonic() - started < 0.05


def test_with_timezone_leaves_the_original_alone() -> None:
    clock = SystemClock("UTC")

    moved = clock.with_timezone("Europe/Paris")

    assert moved is not clock
    assert clock.timezone != PARIS
    assert moved.timezone == PARIS


def test_with_timezone_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = SystemClock("UTC").with_timezone("Nope/Nope")


def test_it_reads_as_the_zone_it_reports_in() -> None:
    assert repr(SystemClock("Europe/Paris")) == "SystemClock(Europe/Paris)"
