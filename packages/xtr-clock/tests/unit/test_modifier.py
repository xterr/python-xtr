from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from xtr_clock import InvalidModifierError, apply_modifier

REFERENCE = datetime(2024, 4, 9, 15, 30, 45, 123456, tzinfo=UTC)
AMSTERDAM = ZoneInfo("Europe/Amsterdam")


def shown(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S.%f")


@pytest.mark.parametrize("modifier", ["now", "  now  ", "NOW"])
def test_now_returns_the_reference_untouched(modifier: str) -> None:
    assert apply_modifier(REFERENCE, modifier) == REFERENCE


@pytest.mark.parametrize(
    ("modifier", "expected"),
    [
        ("+1 day", "2024-04-10 15:30:45.123456"),
        ("-1 day", "2024-04-08 15:30:45.123456"),
        ("1 day", "2024-04-10 15:30:45.123456"),
        ("+2 days", "2024-04-11 15:30:45.123456"),
        ("+1 week", "2024-04-16 15:30:45.123456"),
        ("+1 month", "2024-05-09 15:30:45.123456"),
        ("+1 year", "2025-04-09 15:30:45.123456"),
        ("+3 hours", "2024-04-09 18:30:45.123456"),
        ("+90 minutes", "2024-04-09 17:00:45.123456"),
        ("+15 seconds", "2024-04-09 15:31:00.123456"),
        ("+500 milliseconds", "2024-04-09 15:30:45.623456"),
        ("+1 microsecond", "2024-04-09 15:30:45.123457"),
    ],
)
def test_an_offset_moves_by_one_unit(modifier: str, expected: str) -> None:
    assert shown(apply_modifier(REFERENCE, modifier)) == expected


@pytest.mark.parametrize(
    ("modifier", "expected"),
    [
        ("+1 day 2 hours", "2024-04-10 17:30:45.123456"),
        ("+1 day, 2 hours", "2024-04-10 17:30:45.123456"),
        ("+1 year 1 month 1 day", "2025-05-10 15:30:45.123456"),
        ("+1 day -3 hours", "2024-04-10 12:30:45.123456"),
    ],
)
def test_units_may_be_chained(modifier: str, expected: str) -> None:
    assert shown(apply_modifier(REFERENCE, modifier)) == expected


@pytest.mark.parametrize(
    ("modifier", "expected"),
    [
        ("-2 hours 30 minutes", "2024-04-09 13:00:45.123456"),
        ("-1 hour 30 minutes", "2024-04-09 14:00:45.123456"),
        ("-1 day 2 hours", "2024-04-08 13:30:45.123456"),
        ("-1 month 1 day", "2024-03-08 15:30:45.123456"),
    ],
)
def test_a_term_with_no_sign_keeps_going_the_way_the_last_one_did(
    modifier: str,
    expected: str,
) -> None:
    assert shown(apply_modifier(REFERENCE, modifier)) == expected


@pytest.mark.parametrize(
    ("modifier", "expected"),
    [
        ("-2 hours +30 minutes", "2024-04-09 14:00:45.123456"),
        ("+1 day -3 hours +30 minutes", "2024-04-10 13:00:45.123456"),
    ],
)
def test_writing_a_sign_again_turns_the_offset_around(modifier: str, expected: str) -> None:
    assert shown(apply_modifier(REFERENCE, modifier)) == expected


def test_a_trailing_ago_negates_a_whole_chain() -> None:
    assert shown(apply_modifier(REFERENCE, "1 hour 30 minutes ago")) == "2024-04-09 14:00:45.123456"


@pytest.mark.parametrize(
    ("modifier", "expected"),
    [
        ("+1 hr", "2024-04-09 16:30:45.123456"),
        ("+2 hrs", "2024-04-09 17:30:45.123456"),
        ("+1 min", "2024-04-09 15:31:45.123456"),
        ("+2 mins", "2024-04-09 15:32:45.123456"),
        ("+1 sec", "2024-04-09 15:30:46.123456"),
        ("+2 secs", "2024-04-09 15:30:47.123456"),
        ("+1 yr", "2025-04-09 15:30:45.123456"),
        ("+1 msec", "2024-04-09 15:30:45.124456"),
        ("+1 usec", "2024-04-09 15:30:45.123457"),
    ],
)
def test_short_unit_spellings_are_understood(modifier: str, expected: str) -> None:
    assert shown(apply_modifier(REFERENCE, modifier)) == expected


@pytest.mark.parametrize(
    ("modifier", "expected"),
    [
        ("2 days ago", "2024-04-07 15:30:45.123456"),
        ("3 hours ago", "2024-04-09 12:30:45.123456"),
        ("1 month ago", "2024-03-09 15:30:45.123456"),
    ],
)
def test_ago_reads_an_offset_backwards(modifier: str, expected: str) -> None:
    assert shown(apply_modifier(REFERENCE, modifier)) == expected


@pytest.mark.parametrize(
    ("modifier", "expected"),
    [
        ("today", "2024-04-09 00:00:00.000000"),
        ("midnight", "2024-04-09 00:00:00.000000"),
        ("noon", "2024-04-09 12:00:00.000000"),
        ("tomorrow", "2024-04-10 00:00:00.000000"),
        ("yesterday", "2024-04-08 00:00:00.000000"),
        ("TOMORROW", "2024-04-10 00:00:00.000000"),
    ],
)
def test_a_keyword_lands_on_a_boundary_of_the_day(modifier: str, expected: str) -> None:
    assert shown(apply_modifier(REFERENCE, modifier)) == expected


@pytest.mark.parametrize(
    ("modifier", "expected"),
    [
        ("2022-01-28", "2022-01-28 00:00:00.000000"),
        ("2022-01-28 15:00", "2022-01-28 15:00:00.000000"),
        ("2022-01-28 15:00:30", "2022-01-28 15:00:30.000000"),
        ("2022-01-28T15:00:30.500", "2022-01-28 15:00:30.500000"),
        ("2024-04", "2024-04-01 00:00:00.000000"),
        ("2024-12", "2024-12-01 00:00:00.000000"),
    ],
)
def test_an_absolute_datetime_replaces_the_reference(modifier: str, expected: str) -> None:
    assert shown(apply_modifier(REFERENCE, modifier)) == expected


def test_a_date_with_no_time_starts_at_midnight() -> None:
    assert shown(apply_modifier(REFERENCE, "2024-04-09")) == "2024-04-09 00:00:00.000000"


def test_an_absolute_datetime_with_no_zone_is_read_in_the_references_zone() -> None:
    reference = REFERENCE.astimezone(AMSTERDAM)

    assert apply_modifier(reference, "2022-06-01 12:00:00").utcoffset() == AMSTERDAM.utcoffset(
        datetime(2022, 6, 1, 12),
    )


def test_an_absolute_datetime_carrying_its_own_offset_keeps_it() -> None:
    moment = apply_modifier(REFERENCE, "2022-01-28T15:00:00+02:00")

    assert moment.isoformat() == "2022-01-28T15:00:00+02:00"


def test_a_bare_timezone_moves_the_reference_without_moving_the_instant() -> None:
    moment = apply_modifier(REFERENCE, "Europe/Paris")

    assert moment == REFERENCE
    assert moment.tzinfo == ZoneInfo("Europe/Paris")


def test_a_trailing_timezone_is_applied_before_the_rest_of_the_modifier() -> None:
    reference = datetime(2010, 1, 28, 15, 0, tzinfo=UTC)

    moment = apply_modifier(reference, "+1 day Europe/Paris")

    assert moment.strftime("%Y-%m-%d %H:%M:%S") == "2010-01-29 16:00:00"


def test_a_trailing_timezone_applies_to_an_absolute_datetime_too() -> None:
    moment = apply_modifier(REFERENCE, "2022-01-28 15:00:00 Europe/Paris")

    assert moment.strftime("%Y-%m-%d %H:%M:%S") == "2022-01-28 15:00:00"
    assert moment.tzinfo == ZoneInfo("Europe/Paris")


def test_adding_a_month_clamps_to_the_end_of_a_shorter_one() -> None:
    january = datetime(2024, 1, 31, 12, tzinfo=UTC)

    assert shown(apply_modifier(january, "+1 month")) == "2024-02-29 12:00:00.000000"


def test_clamping_is_not_associative_at_the_end_of_a_month() -> None:
    january = datetime(2025, 1, 31, 12, tzinfo=UTC)

    once = apply_modifier(january, "+2 months")
    twice = apply_modifier(apply_modifier(january, "+1 month"), "+1 month")

    assert shown(once) == "2025-03-31 12:00:00.000000"
    assert shown(twice) == "2025-03-28 12:00:00.000000"


def test_subtracting_a_month_clamps_the_same_way() -> None:
    march = datetime(2024, 3, 31, 12, tzinfo=UTC)

    assert shown(apply_modifier(march, "-1 month")) == "2024-02-29 12:00:00.000000"


def test_adding_a_day_keeps_the_wall_clock_across_a_daylight_saving_change() -> None:
    eve = datetime(2025, 3, 30, 1, tzinfo=AMSTERDAM)

    assert apply_modifier(eve, "+1 day").isoformat() == "2025-03-31T01:00:00+02:00"


def test_adding_hours_keeps_the_elapsed_time_across_a_daylight_saving_change() -> None:
    eve = datetime(2025, 3, 30, 1, tzinfo=AMSTERDAM)

    assert apply_modifier(eve, "+24 hours").isoformat() == "2025-03-31T02:00:00+02:00"


def test_a_wall_clock_the_zone_skipped_is_reported_as_the_hour_that_replaced_it() -> None:
    before = datetime(2025, 3, 29, 2, 30, tzinfo=AMSTERDAM)

    moved = apply_modifier(before, "+1 day")

    assert moved.isoformat() == "2025-03-30T03:30:00+02:00"


def test_a_naive_reference_is_moved_without_being_given_a_zone() -> None:
    naive = datetime(2024, 4, 9, 15, 30)

    moved = apply_modifier(naive, "+3 hours")

    assert moved.tzinfo is None
    assert shown(moved) == "2024-04-09 18:30:00.000000"


@pytest.mark.parametrize(
    "modifier",
    [
        "",
        "   ",
        "+1 dya",
        "Halloween",
        "+1",
        "day",
        "ago",
        "next tuesday",
        "1 fortnight",
        "2024-13",
    ],
)
def test_a_modifier_the_grammar_cannot_read_is_refused(modifier: str) -> None:
    with pytest.raises(InvalidModifierError) as caught:
        _ = apply_modifier(REFERENCE, modifier)

    assert caught.value.modifier == modifier


def test_the_error_is_also_a_value_error() -> None:
    with pytest.raises(ValueError, match="cannot be read"):
        _ = apply_modifier(REFERENCE, "+1 dya")


@pytest.mark.parametrize("modifier", ["+1 m", "+1 h", "+1 d"])
def test_an_ambiguous_single_letter_unit_is_refused_rather_than_guessed(modifier: str) -> None:
    with pytest.raises(InvalidModifierError):
        _ = apply_modifier(REFERENCE, modifier)
