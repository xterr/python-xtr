from __future__ import annotations

import asyncio
import threading
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from xtr_clock import (
    Clock,
    ClockInterface,
    DatePoint,
    InvalidTimezoneError,
    MockClock,
    SystemClock,
)

PARIS = ZoneInfo("Europe/Paris")
FIXED = datetime(2001, 9, 9, 1, 46, 40, tzinfo=UTC)


class NowOnly:
    """A clock from somewhere else: it can say the time and nothing more."""

    def now(self) -> datetime:
        return FIXED


class NaiveNowOnly:
    """A foreign clock that has never heard of timezones."""

    def now(self) -> datetime:
        return datetime(2001, 9, 9, 1, 46, 40)


def test_the_clock_in_force_reads_the_system_by_default() -> None:
    assert isinstance(Clock.get(), SystemClock)


def test_the_default_clock_is_built_once_and_kept() -> None:
    assert Clock.get() is Clock.get()


def test_a_full_clock_is_installed_as_itself() -> None:
    clock = MockClock()

    Clock.set(clock)

    assert Clock.get() is clock


def test_a_clock_that_can_only_say_the_time_is_wrapped() -> None:
    Clock.set(NowOnly())

    installed = Clock.get()

    assert isinstance(installed, Clock)
    assert installed.now() == FIXED


def test_using_installs_a_clock_and_takes_it_away_again() -> None:
    before = Clock.get()
    clock = MockClock()

    with Clock.using(clock) as installed:
        assert Clock.get() is clock
        assert installed is clock

    assert Clock.get() is before


def test_using_takes_the_clock_away_even_when_the_block_raises() -> None:
    before = Clock.get()

    with pytest.raises(RuntimeError), Clock.using(MockClock()):
        raise RuntimeError

    assert Clock.get() is before


def test_using_nests() -> None:
    outer = MockClock("2001-01-01 00:00:00")
    inner = MockClock("2002-02-02 00:00:00")

    with Clock.using(outer):
        with Clock.using(inner):
            assert Clock.get() is inner
        assert Clock.get() is outer


def test_using_wraps_a_clock_that_can_only_say_the_time() -> None:
    with Clock.using(NowOnly()) as installed:
        assert isinstance(installed, Clock)
        assert installed.now() == FIXED


def test_a_clock_installed_with_set_is_visible_in_a_thread_started_later() -> None:
    Clock.set(MockClock(FIXED))
    seen: list[datetime] = []

    thread = threading.Thread(target=lambda: seen.append(Clock.get().now()))
    thread.start()
    thread.join()

    assert seen == [FIXED]


def test_a_clock_installed_for_a_scope_is_visible_in_a_thread_started_inside_it() -> None:
    seen: list[datetime] = []

    with Clock.using(MockClock(FIXED)):
        thread = threading.Thread(target=lambda: seen.append(Clock.get().now()))
        thread.start()
        thread.join()

    assert seen == [FIXED]


@pytest.mark.anyio
async def test_a_clock_installed_inside_a_task_does_not_leak_out_of_it() -> None:
    before = Clock.get()

    async def inside() -> None:
        with Clock.using(MockClock(FIXED)):
            assert Clock.get().now() == FIXED

    await asyncio.ensure_future(inside())

    assert Clock.get() is before


def test_an_instance_reads_the_clock_it_wraps() -> None:
    assert Clock(NowOnly()).now() == FIXED


def test_an_instance_answers_with_a_date_point() -> None:
    assert type(Clock(NowOnly()).now()) is DatePoint


def test_a_naive_foreign_reading_is_given_a_zone() -> None:
    assert Clock(NaiveNowOnly()).now().tzinfo is not None


def test_an_instance_wrapping_nothing_follows_the_clock_in_force() -> None:
    following = Clock()

    with Clock.using(MockClock(FIXED)):
        assert following.now() == FIXED


def test_an_instance_wrapping_nothing_is_read_afresh_each_time() -> None:
    following = Clock()

    with Clock.using(MockClock("2001-01-01 00:00:00")):
        first = following.now()
    with Clock.using(MockClock("2002-02-02 00:00:00")):
        second = following.now()

    assert first.year == 2001
    assert second.year == 2002


def test_an_instance_installed_as_the_clock_in_force_does_not_ask_itself() -> None:
    Clock.set(Clock())

    assert Clock.get().now() is not None


def test_a_pinned_zone_moves_the_reading_without_moving_the_instant() -> None:
    clock = Clock(NowOnly(), "Europe/Paris")

    assert clock.now() == FIXED
    assert clock.now().tzinfo == PARIS


def test_no_pinned_zone_keeps_whatever_the_wrapped_clock_reported() -> None:
    assert Clock(NowOnly()).timezone is None


def test_it_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = Clock(NowOnly(), "Nope/Nope")


def test_with_timezone_leaves_the_original_alone() -> None:
    clock = Clock(NowOnly())

    moved = clock.with_timezone("Europe/Paris")

    assert moved is not clock
    assert clock.timezone is None
    assert moved.timezone == PARIS


def test_with_timezone_keeps_reading_the_same_wrapped_clock() -> None:
    assert Clock(NowOnly()).with_timezone("Europe/Paris").now() == FIXED


def test_with_timezone_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = Clock(NowOnly()).with_timezone("Nope/Nope")


def test_sleep_is_handed_to_a_wrapped_clock_that_knows_how() -> None:
    mock = MockClock("2024-04-09 12:00:00")

    Clock(mock).sleep(3600)

    assert mock.now().isoformat() == "2024-04-09T13:00:00+00:00"


def test_sleep_falls_back_to_real_time_for_a_clock_that_only_says_the_time() -> None:
    started = time.monotonic()

    Clock(NowOnly()).sleep(0.05)

    assert time.monotonic() - started >= 0.05


def test_sleep_on_an_instance_wrapping_nothing_reaches_the_clock_in_force() -> None:
    mock = MockClock("2024-04-09 12:00:00")
    following = Clock()

    with Clock.using(mock):
        following.sleep(3600)

    assert mock.now().isoformat() == "2024-04-09T13:00:00+00:00"


@pytest.mark.anyio
async def test_sleep_async_is_handed_to_a_wrapped_clock_that_knows_how() -> None:
    mock = MockClock("2024-04-09 12:00:00")

    await Clock(mock).sleep_async(3600)

    assert mock.now().isoformat() == "2024-04-09T13:00:00+00:00"


@pytest.mark.anyio
async def test_sleep_async_falls_back_to_real_time_for_a_now_only_clock() -> None:
    started = time.monotonic()

    await Clock(NowOnly()).sleep_async(0.05)

    assert time.monotonic() - started >= 0.05


def test_an_instance_satisfies_the_full_contract() -> None:
    assert isinstance(Clock(NowOnly()), ClockInterface)


def test_it_reads_as_what_it_wraps() -> None:
    assert repr(Clock(None)) == "Clock(None)"
    assert repr(Clock(None, "UTC")) == "Clock(None, UTC)"
