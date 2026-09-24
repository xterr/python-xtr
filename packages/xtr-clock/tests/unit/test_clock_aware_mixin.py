from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import final

from xtr_clock import Clock, ClockAwareMixin, DatePoint, MockClock, SystemClock

FIXED = datetime(2001, 9, 9, 1, 46, 40, tzinfo=UTC)


class Service(ClockAwareMixin):
    """A plain class that needs the time."""


@dataclass
class Record(ClockAwareMixin):
    """A dataclass: the mixin defines no __init__, so this composes."""

    name: str


def test_it_reads_the_clock_in_force_until_it_is_given_one() -> None:
    assert isinstance(Service().clock, SystemClock)


def test_it_reads_the_clock_installed_for_a_scope() -> None:
    service = Service()

    with Clock.using(MockClock(FIXED)):
        assert service.now() == FIXED


def test_a_clock_it_is_given_wins_over_the_one_in_force() -> None:
    service = Service()
    service.set_clock(MockClock(FIXED))

    with Clock.using(MockClock("2099-01-01 00:00:00")):
        assert service.now() == FIXED


def test_the_clock_it_was_given_is_the_one_it_reports() -> None:
    service = Service()
    clock = MockClock()

    service.set_clock(clock)

    assert service.clock is clock


def test_now_answers_with_a_date_point() -> None:
    assert type(Service().now()) is DatePoint


def test_now_follows_the_clock_it_was_given_as_that_clock_moves() -> None:
    service = Service()
    clock = MockClock("2024-04-09 12:00:00")
    service.set_clock(clock)

    first = service.now()
    clock.sleep(3600)

    assert (service.now() - first).total_seconds() == 3600


def test_two_instances_keep_their_own_clocks() -> None:
    first = Service()
    second = Service()

    first.set_clock(MockClock(FIXED))

    assert first.now() == FIXED
    assert second.clock is not first.clock


def test_it_composes_with_a_dataclass() -> None:
    record = Record(name="invoice")
    record.set_clock(MockClock(FIXED))

    assert record.name == "invoice"
    assert record.now() == FIXED


def test_it_adds_no_instance_dictionary_to_a_class_that_has_none() -> None:
    @final
    class Slotted(ClockAwareMixin):
        __slots__ = ()

    assert not hasattr(Slotted(), "__dict__")
