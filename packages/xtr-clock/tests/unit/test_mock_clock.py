from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from xtr_clock import (
    Clock,
    DatePoint,
    InvalidModifierError,
    InvalidTimezoneError,
    MockClock,
)

PARIS = ZoneInfo("Europe/Paris")
AMSTERDAM = ZoneInfo("Europe/Amsterdam")


def test_it_freezes_at_the_current_instant_in_utc_by_default() -> None:
    before = datetime.now(UTC)
    clock = MockClock()
    after = datetime.now(UTC)

    assert before <= clock.now() <= after
    assert clock.timezone == UTC


def test_the_default_zone_is_the_same_object_as_naming_utc() -> None:
    assert MockClock().timezone is MockClock("now", "UTC").timezone


def test_it_freezes_at_an_absolute_datetime_written_as_a_string() -> None:
    assert MockClock("2022-06-20 00:00:00").now().isoformat() == "2022-06-20T00:00:00+00:00"


def test_it_freezes_at_a_datetime_and_keeps_that_datetimes_zone() -> None:
    moment = datetime(2024, 4, 9, 15, tzinfo=PARIS)

    clock = MockClock(moment)

    assert clock.now() == moment
    assert clock.timezone is PARIS


def test_a_bare_timezone_string_reads_the_current_instant_in_that_zone() -> None:
    assert MockClock("Europe/Paris").timezone == PARIS


def test_a_named_zone_moves_the_reading_without_moving_the_instant() -> None:
    moment = datetime(2024, 4, 9, 15, tzinfo=UTC)

    clock = MockClock(moment, "Europe/Paris")

    assert clock.now() == moment
    assert clock.now().strftime("%H:%M") == "17:00"


def test_it_accepts_an_already_resolved_zone() -> None:
    assert MockClock("now", PARIS).timezone is PARIS


def test_a_relative_string_is_read_against_the_clock_already_in_force() -> None:
    with Clock.using(MockClock("2021-12-19 00:00:00")):
        assert MockClock("+1 day").now().date().isoformat() == "2021-12-20"


def test_now_answers_with_a_date_point() -> None:
    assert type(MockClock().now()) is DatePoint


def test_now_answers_the_same_instant_every_time() -> None:
    clock = MockClock()

    assert clock.now() == clock.now()


def test_now_does_not_move_while_real_time_passes() -> None:
    clock = MockClock()

    first = clock.now()
    time.sleep(0.01)

    assert clock.now() == first


def test_sleep_moves_the_clock_and_costs_no_real_time() -> None:
    clock = MockClock("2024-04-09 12:00:00")

    started = time.monotonic()
    clock.sleep(3600)

    assert clock.now().isoformat() == "2024-04-09T13:00:00+00:00"
    assert time.monotonic() - started < 0.05


def test_sleep_carries_fractions_of_a_second() -> None:
    clock = MockClock(datetime(2112, 9, 17, 23, 53, 0, 999000, tzinfo=UTC))

    clock.sleep(2.002001)

    assert clock.now().strftime("%Y-%m-%d %H:%M:%S.%f") == "2112-09-17 23:53:03.001001"


def test_sleep_keeps_the_zone_it_reports_in() -> None:
    clock = MockClock("2024-04-09 12:00:00", "Europe/Paris")

    clock.sleep(60)

    assert clock.timezone == PARIS


@pytest.mark.parametrize("seconds", [0, -1, -10.5])
def test_sleep_for_nothing_or_less_does_not_move_the_clock(seconds: float) -> None:
    clock = MockClock("2024-04-09 12:00:00")

    clock.sleep(seconds)

    assert clock.now().isoformat() == "2024-04-09T12:00:00+00:00"


def test_sleeping_through_a_daylight_saving_change_counts_elapsed_time() -> None:
    clock = MockClock(datetime(2025, 3, 30, 1, tzinfo=AMSTERDAM))

    clock.sleep(3600)

    assert clock.now().isoformat() == "2025-03-30T03:00:00+02:00"


@pytest.mark.anyio
async def test_sleep_async_moves_the_clock_and_costs_no_real_time() -> None:
    clock = MockClock("2024-04-09 12:00:00")

    started = time.monotonic()
    await clock.sleep_async(3600)

    assert clock.now().isoformat() == "2024-04-09T13:00:00+00:00"
    assert time.monotonic() - started < 0.05


@pytest.mark.anyio
async def test_sleep_async_hands_control_back_so_other_tasks_get_a_turn() -> None:
    clock = MockClock("2024-04-09 12:00:00")
    order: list[str] = []

    async def other() -> None:
        order.append("other")

    task = asyncio.ensure_future(other())
    await clock.sleep_async(1)
    order.append("after")
    await task

    assert order == ["other", "after"]


@pytest.mark.anyio
async def test_sleep_async_for_nothing_does_not_move_the_clock() -> None:
    clock = MockClock("2024-04-09 12:00:00")

    await clock.sleep_async(0)

    assert clock.now().isoformat() == "2024-04-09T12:00:00+00:00"


@pytest.mark.parametrize(
    ("modifier", "expected"),
    [
        ("+2 days", "2112-09-19 23:53:00.999000"),
        ("2112-09-17 23:53:03.001", "2112-09-17 23:53:03.001000"),
        ("tomorrow", "2112-09-18 00:00:00.000000"),
    ],
)
def test_modify_moves_the_clock(modifier: str, expected: str) -> None:
    clock = MockClock(datetime(2112, 9, 17, 23, 53, 0, 999000, tzinfo=UTC))

    clock.modify(modifier)

    assert clock.now().strftime("%Y-%m-%d %H:%M:%S.%f") == expected


def test_modify_keeps_the_zone_it_reports_in() -> None:
    clock = MockClock("2024-04-09 12:00:00", "Europe/Paris")

    clock.modify("+2 days")

    assert clock.timezone == PARIS


@pytest.mark.parametrize("modifier", ["Halloween", ""])
def test_modify_refuses_a_modifier_the_grammar_cannot_read(modifier: str) -> None:
    clock = MockClock("2024-04-09 12:00:00")

    with pytest.raises(InvalidModifierError):
        clock.modify(modifier)


def test_a_string_the_grammar_cannot_read_is_refused_at_construction() -> None:
    with pytest.raises(InvalidModifierError):
        _ = MockClock("Halloween")


def test_it_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = MockClock("now", "Nope/Nope")


def test_with_timezone_leaves_the_original_alone() -> None:
    clock = MockClock("2024-04-09 12:00:00")

    moved = clock.with_timezone("Europe/Paris")

    assert moved is not clock
    assert clock.timezone == UTC
    assert moved.timezone == PARIS


def test_with_timezone_keeps_the_instant_it_is_frozen_at() -> None:
    clock = MockClock("2024-04-09 12:00:00")

    assert clock.with_timezone("Europe/Paris").now() == clock.now()


def test_moving_a_copy_does_not_move_the_original() -> None:
    clock = MockClock("2024-04-09 12:00:00")
    moved = clock.with_timezone("Europe/Paris")

    moved.sleep(3600)

    assert clock.now().isoformat() == "2024-04-09T12:00:00+00:00"


def test_with_timezone_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = MockClock().with_timezone("Nope/Nope")


def test_it_reads_as_the_instant_it_is_frozen_at() -> None:
    clock = MockClock("2024-04-09 12:00:00")

    assert repr(clock) == "MockClock('2024-04-09T12:00:00+00:00')"
