from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from xtr_clock import (
    Clock,
    DatePoint,
    InvalidModifierError,
    InvalidTimezoneError,
    MockClock,
    now,
)

PARIS = ZoneInfo("Europe/Paris")


def test_it_answers_with_a_date_point() -> None:
    assert type(now()) is DatePoint


def test_it_sits_between_two_readings_of_the_system_clock() -> None:
    before = datetime.now(UTC)
    moment = now()
    after = datetime.now(UTC)

    assert before <= moment <= after


def test_it_reads_the_clock_in_force() -> None:
    with Clock.using(MockClock("2010-01-28 15:00:00")):
        assert now().isoformat() == "2010-01-28T15:00:00+00:00"


def test_it_follows_the_clock_in_force_as_that_clock_moves() -> None:
    with Clock.using(MockClock("2010-01-28 15:00:00")) as clock:
        assert isinstance(clock, MockClock)
        clock.sleep(3600)

        assert now().isoformat() == "2010-01-28T16:00:00+00:00"


@pytest.mark.parametrize(
    ("modifier", "expected"),
    [
        ("now", "2010-01-28 15:00:00"),
        ("+1 hour", "2010-01-28 16:00:00"),
        ("tomorrow", "2010-01-29 00:00:00"),
        ("2023-08-14", "2023-08-14 00:00:00"),
        ("2023-08-14 09:30", "2023-08-14 09:30:00"),
    ],
)
def test_a_modifier_is_read_against_the_clock_in_force(modifier: str, expected: str) -> None:
    with Clock.using(MockClock("2010-01-28 15:00:00")):
        assert now(modifier).strftime("%Y-%m-%d %H:%M:%S") == expected


def test_a_timezone_modifier_keeps_the_instant_and_changes_the_zone() -> None:
    with Clock.using(MockClock("2010-01-28 15:00:00")) as clock:
        moment = now("Europe/Paris")

        assert moment == clock.now()
        assert moment.tzinfo == PARIS


def test_a_named_zone_is_applied_before_the_modifier() -> None:
    with Clock.using(MockClock("2010-01-28 15:00:00")):
        assert now("+1 day", "Europe/Paris").strftime("%Y-%m-%d %H:%M") == "2010-01-29 16:00"


def test_a_named_zone_alone_moves_the_reading() -> None:
    with Clock.using(MockClock("2010-01-28 15:00:00")):
        assert now(timezone="Europe/Paris").strftime("%H:%M") == "16:00"


def test_it_refuses_a_modifier_the_grammar_cannot_read() -> None:
    with pytest.raises(InvalidModifierError):
        _ = now("invalid date")


def test_it_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = now("now", "Nope/Nope")
