from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_stopwatch import EventNotStartedError, Section, UnknownEventError
from xtr_stopwatch._milliseconds import now_ms

if TYPE_CHECKING:
    from xtr_clock import MockClock


def test_events_of_a_section_share_its_origin(clock: MockClock) -> None:
    section = Section(now_ms(clock), clock)
    clock.sleep(0.001)
    first = section.start_event("a", None)
    clock.sleep(0.001)
    second = section.start_event("b", "orm")

    assert first.origin == second.origin
    assert second.get_start_time() == pytest.approx(2.0)


def test_the_root_measures_each_event_from_its_first_start(clock: MockClock) -> None:
    root = Section(None, clock)
    clock.sleep(0.005)

    event = root.start_event("a", None)

    assert event.origin == pytest.approx(now_ms(clock))


def test_starting_an_event_twice_is_one_event(clock: MockClock) -> None:
    section = Section(now_ms(clock), clock)

    first = section.start_event("a", None)
    _ = section.stop_event("a")
    second = section.start_event("a", None)

    assert first is second
    assert section.is_event_started("a")


def test_an_event_this_section_never_started_is_not_running(clock: MockClock) -> None:
    section = Section(now_ms(clock), clock)

    assert not section.is_event_started("a")
    with pytest.raises(EventNotStartedError):
        _ = section.stop_event("a")


def test_an_unknown_event_is_refused(clock: MockClock) -> None:
    with pytest.raises(UnknownEventError, match='event "a" is not known'):
        _ = Section(None, clock).get_event("a")


def test_a_lap_restarts_the_event(clock: MockClock) -> None:
    section = Section(now_ms(clock), clock)
    _ = section.start_event("a", None)

    event = section.lap_event("a")

    assert event.is_started()
    assert len(event.get_periods()) == 1


def test_opening_by_an_unknown_id_adds_a_child_and_a_known_one_reopens_it(
    clock: MockClock,
) -> None:
    root = Section(None, clock)

    child = root.open(None).set_id("one")

    assert root.open("one") is child
    assert root.open("two") is not child
    assert root.get("one") is child
    assert root.get("missing") is None
    assert len(root.children) == 2


def test_events_are_listed_in_the_order_they_first_started(clock: MockClock) -> None:
    section = Section(now_ms(clock), clock)
    _ = section.start_event("b", None)
    _ = section.start_event("a", None)

    assert list(section.get_events()) == ["b", "a"]
    assert section.get_event("a").name == "a"


def test_a_section_without_a_clock_still_times() -> None:
    section = Section()

    assert section.start_event("a", None).stop().get_duration() >= 0.0
    assert repr(section) == "Section(id=None, events=1, children=0)"
