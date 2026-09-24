from __future__ import annotations

import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from xtr_clock import Clock, DatePoint, InvalidModifierError, MockClock, SystemClock, now
from xtr_clock.testing import mock_time

PARIS = ZoneInfo("Europe/Paris")


def test_it_installs_a_frozen_clock_and_takes_it_away_again() -> None:
    before = Clock.get()

    with mock_time() as clock:
        assert Clock.get() is clock
        assert isinstance(clock, MockClock)

    assert Clock.get() is before
    assert isinstance(Clock.get(), SystemClock)


def test_it_takes_the_clock_away_even_when_the_block_raises() -> None:
    before = Clock.get()

    with pytest.raises(RuntimeError), mock_time():
        raise RuntimeError

    assert Clock.get() is before


def test_time_does_not_pass_inside_the_block() -> None:
    with mock_time():
        first = now()
        time.sleep(0.01)

        assert now() == first


def test_the_clock_it_yields_can_be_moved_forward() -> None:
    with mock_time("2024-04-09 12:00:00") as clock:
        clock.sleep(3600)

        assert now().isoformat() == "2024-04-09T13:00:00+00:00"


def test_the_clock_it_yields_can_be_modified() -> None:
    with mock_time("2024-04-09 12:00:00") as clock:
        clock.modify("+2 days")

        assert now().date().isoformat() == "2024-04-11"


def test_it_freezes_at_an_absolute_datetime_written_as_a_string() -> None:
    with mock_time("2021-12-19 00:00:00"):
        assert now().date().isoformat() == "2021-12-19"


def test_it_freezes_at_a_datetime() -> None:
    moment = datetime(2021, 12, 19, tzinfo=UTC)

    with mock_time(moment):
        assert now() == moment


def test_it_freezes_at_the_current_instant_by_default() -> None:
    before = datetime.now(UTC)

    with mock_time():
        assert before <= now() <= datetime.now(UTC)


def test_it_reports_in_a_named_zone() -> None:
    with mock_time("2024-04-09 12:00:00", "Europe/Paris"):
        assert now().tzinfo == PARIS


def test_a_relative_modifier_composes_with_a_clock_already_frozen() -> None:
    with mock_time(datetime(2021, 12, 19, tzinfo=UTC)):
        assert now().date().isoformat() == "2021-12-19"

        with mock_time("+1 day"):
            assert now().date().isoformat() == "2021-12-20"

        assert now().date().isoformat() == "2021-12-19"


def test_it_reaches_code_that_reads_the_date_point_directly() -> None:
    with mock_time("2010-01-28 15:00:00"):
        assert DatePoint.now().isoformat() == "2010-01-28T15:00:00+00:00"


def test_it_reaches_code_that_parses_a_relative_modifier() -> None:
    with mock_time("2010-01-28 15:00:00"):
        assert DatePoint.parse("+1 day").isoformat() == "2010-01-29T15:00:00+00:00"


def test_it_refuses_a_modifier_the_grammar_cannot_read() -> None:
    with pytest.raises(InvalidModifierError), mock_time("Halloween"):
        pass


@pytest.mark.anyio
async def test_it_freezes_time_inside_a_coroutine() -> None:
    with mock_time("2024-04-09 12:00:00") as clock:
        first = now()
        await clock.sleep_async(3600)

        assert (now() - first).total_seconds() == 3600
