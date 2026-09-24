from __future__ import annotations

import copy
import pickle
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import pytest

from xtr_clock import (
    Clock,
    DatePoint,
    InvalidModifierError,
    InvalidTimezoneError,
    MockClock,
)

if TYPE_CHECKING:
    from collections.abc import Callable

PARIS = ZoneInfo("Europe/Paris")
AMSTERDAM = ZoneInfo("Europe/Amsterdam")


class Stamp(DatePoint):
    """A subclass, to prove the type that comes back is the type that went in."""


def test_a_date_point_is_a_datetime() -> None:
    assert isinstance(DatePoint(2024, 4, 9, tzinfo=UTC), datetime)


def test_a_construction_with_no_zone_is_given_the_local_one() -> None:
    assert DatePoint(2024, 4, 9).tzinfo is not None


def test_a_construction_with_a_zone_keeps_it() -> None:
    assert DatePoint(2024, 4, 9, tzinfo=PARIS).tzinfo is PARIS


def test_every_field_is_carried_through_the_constructor() -> None:
    point = DatePoint(2024, 4, 9, 15, 30, 45, 123456, UTC)

    assert point.isoformat() == "2024-04-09T15:30:45.123456+00:00"


def test_fold_is_carried_through_the_constructor() -> None:
    assert DatePoint(2025, 10, 26, 2, 30, tzinfo=AMSTERDAM, fold=1).fold == 1


OPERATIONS: list[Callable[[DatePoint], datetime]] = [
    lambda point: point.replace(hour=3),
    lambda point: point + timedelta(days=1),
    lambda point: point - timedelta(days=1),
    lambda point: point.astimezone(PARIS),
    lambda point: point.modify("+1 week"),
    lambda point: point.with_timezone("Europe/Paris"),
]

AWARE_CONSTRUCTORS: list[Callable[[], datetime]] = [
    lambda: DatePoint.fromisoformat("2024-04-09T15:00:00+00:00"),
    lambda: DatePoint.fromtimestamp(0, UTC),
    lambda: DatePoint.strptime("2024-04-09", "%Y-%m-%d"),
    lambda: DatePoint.combine(datetime(2024, 4, 9, tzinfo=UTC).date(), datetime.min.time()),
]

WOULD_BE_NAIVE_CONSTRUCTORS: list[Callable[[], datetime]] = [
    lambda: DatePoint.fromisoformat("2024-04-09T15:00:00"),
    lambda: DatePoint.fromtimestamp(0),
    lambda: DatePoint.strptime("2024-04-09", "%Y-%m-%d"),
]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_an_operation_answers_with_a_date_point(
    operation: Callable[[DatePoint], datetime],
) -> None:
    assert type(operation(DatePoint(2024, 4, 9, 15, tzinfo=UTC))) is DatePoint


@pytest.mark.parametrize("build", AWARE_CONSTRUCTORS)
def test_an_inherited_constructor_answers_with_a_date_point(
    build: Callable[[], datetime],
) -> None:
    assert type(build()) is DatePoint


@pytest.mark.parametrize("build", WOULD_BE_NAIVE_CONSTRUCTORS)
def test_an_inherited_constructor_that_would_be_naive_is_given_the_local_zone(
    build: Callable[[], datetime],
) -> None:
    assert build().tzinfo is not None


def test_a_subclass_stays_its_own_type_through_an_operation() -> None:
    assert type(Stamp(2024, 4, 9, tzinfo=UTC).replace(hour=1)) is Stamp


def test_from_datetime_adopts_an_aware_datetime_without_moving_it() -> None:
    original = datetime(2024, 4, 9, 15, tzinfo=PARIS)

    adopted = DatePoint.from_datetime(original)

    assert adopted == original
    assert adopted.tzinfo is PARIS


def test_from_datetime_reads_a_naive_datetime_as_local_time() -> None:
    adopted = DatePoint.from_datetime(datetime(2024, 4, 9, 15))

    assert adopted.tzinfo is not None
    assert adopted.strftime("%H:%M") == "15:00"


def test_from_datetime_returns_a_date_point_unchanged() -> None:
    point = DatePoint(2024, 4, 9, tzinfo=UTC)

    assert DatePoint.from_datetime(point) is point


def test_from_datetime_carries_fold() -> None:
    ambiguous = datetime(2025, 10, 26, 2, 30, tzinfo=AMSTERDAM, fold=1)

    assert DatePoint.from_datetime(ambiguous).fold == 1


def test_now_reads_the_clock_in_force_rather_than_the_operating_system() -> None:
    with Clock.using(MockClock("2010-01-28 15:00:00")):
        assert DatePoint.now().isoformat() == "2010-01-28T15:00:00+00:00"


def test_now_reads_the_clock_in_force_into_a_requested_zone() -> None:
    with Clock.using(MockClock("2010-01-28 15:00:00")):
        assert DatePoint.now(PARIS).isoformat() == "2010-01-28T16:00:00+01:00"


def test_parse_reads_a_modifier_against_the_clock_in_force() -> None:
    with Clock.using(MockClock("2010-01-28 15:00:00")):
        assert DatePoint.parse("+1 day").isoformat() == "2010-01-29T15:00:00+00:00"


def test_parse_reads_a_modifier_against_a_reference_it_is_given() -> None:
    reference = datetime(2001, 9, 9, tzinfo=UTC)

    assert DatePoint.parse("+1 day", reference=reference).isoformat() == "2001-09-10T00:00:00+00:00"


def test_parse_reads_the_reference_in_the_zone_it_is_given() -> None:
    reference = datetime(2010, 1, 28, 15, tzinfo=UTC)

    point = DatePoint.parse("+1 day", "Europe/Paris", reference=reference)

    assert point.strftime("%Y-%m-%d %H:%M") == "2010-01-29 16:00"


def test_a_zone_inside_the_modifier_wins_over_the_one_passed_alongside() -> None:
    reference = datetime(2010, 1, 28, 15, tzinfo=UTC)

    point = DatePoint.parse("Asia/Tokyo", "Europe/Paris", reference=reference)

    assert point.tzinfo == ZoneInfo("Asia/Tokyo")


def test_parse_answers_with_a_date_point() -> None:
    assert type(DatePoint.parse("2024-04-09")) is DatePoint


def test_parse_refuses_a_modifier_the_grammar_cannot_read() -> None:
    with pytest.raises(InvalidModifierError):
        _ = DatePoint.parse("Halloween")


def test_parse_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = DatePoint.parse("now", "Nope/Nope")


def test_modify_leaves_the_instant_it_was_called_on_alone() -> None:
    point = DatePoint(2024, 4, 9, 15, tzinfo=UTC)

    moved = point.modify("+1 day")

    assert point.day == 9
    assert moved.day == 10


def test_modify_refuses_a_modifier_the_grammar_cannot_read() -> None:
    with pytest.raises(InvalidModifierError):
        _ = DatePoint(2024, 4, 9, tzinfo=UTC).modify("Halloween")


def test_with_timezone_keeps_the_instant_and_changes_the_wall_clock() -> None:
    point = DatePoint(2024, 4, 9, 15, tzinfo=UTC)

    moved = point.with_timezone("Europe/Paris")

    assert moved == point
    assert moved.strftime("%H:%M") == "17:00"


def test_with_timezone_accepts_an_already_resolved_zone() -> None:
    assert DatePoint(2024, 4, 9, tzinfo=UTC).with_timezone(PARIS).tzinfo is PARIS


def test_with_timezone_refuses_a_zone_this_system_does_not_know() -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = DatePoint(2024, 4, 9, tzinfo=UTC).with_timezone("Nope/Nope")


def round_trip(point: datetime, protocol: int = pickle.HIGHEST_PROTOCOL) -> datetime:
    return cast("datetime", pickle.loads(pickle.dumps(point, protocol)))  # noqa: S301


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_pickling_round_trips_at_every_protocol(protocol: int) -> None:
    point = DatePoint(2024, 4, 9, 15, 30, 45, 123456, PARIS)

    restored = round_trip(point, protocol)

    assert restored == point
    assert type(restored) is DatePoint
    assert restored.tzinfo == PARIS


def test_pickling_carries_fold() -> None:
    ambiguous = DatePoint(2025, 10, 26, 2, 30, tzinfo=AMSTERDAM, fold=1)

    assert round_trip(ambiguous).fold == 1


def test_pickling_a_subclass_restores_the_subclass() -> None:
    assert type(round_trip(Stamp(2024, 4, 9, tzinfo=UTC))) is Stamp


def test_copying_round_trips() -> None:
    point = DatePoint(2024, 4, 9, 15, tzinfo=PARIS)

    assert copy.deepcopy(point) == point
    assert type(copy.copy(point)) is DatePoint


def test_two_instants_in_different_zones_compare_by_the_moment_they_name() -> None:
    utc = DatePoint(2024, 4, 9, 15, tzinfo=UTC)
    paris = DatePoint(2024, 4, 9, 17, tzinfo=PARIS)

    assert utc == paris
