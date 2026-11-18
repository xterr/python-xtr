from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import anyio.lowlevel
import pytest

from xtr_stopwatch import (
    ROOT,
    SECTION_CATEGORY,
    SECTION_CHILD_EVENT,
    SECTION_EVENT,
    EventNotStartedError,
    NoStartedSectionError,
    Stopwatch,
    UnknownSectionError,
)

if TYPE_CHECKING:
    from xtr_clock import MockClock


def test_an_event_is_timed_by_name(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)

    _ = stopwatch.start("load", "orm")
    clock.sleep(0.004)
    event = stopwatch.stop("load")

    assert event.category == "orm"
    assert event.get_duration() == pytest.approx(4.0)
    assert stopwatch.get_event("load") is event
    assert not stopwatch.is_started("load")


def test_a_section_is_stored_under_the_id_it_stops_with(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)

    stopwatch.open_section()
    _ = stopwatch.start("load")
    clock.sleep(0.002)
    _ = stopwatch.stop("load")
    clock.sleep(0.001)
    stopwatch.stop_section("request")

    events = stopwatch.get_section_events("request")
    assert list(events) == [SECTION_EVENT, "load"]
    assert events[SECTION_EVENT].get_duration() == pytest.approx(3.0)
    assert events["load"].get_duration() == pytest.approx(2.0)


def test_the_parent_holds_an_event_spanning_the_child(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)

    stopwatch.open_section()
    clock.sleep(0.005)
    stopwatch.stop_section("request")

    child = stopwatch.get_section_events(ROOT)[SECTION_CHILD_EVENT]
    assert child.category == SECTION_CATEGORY
    assert child.get_duration() == pytest.approx(5.0)


def test_sections_nest(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)

    stopwatch.open_section()
    stopwatch.open_section()
    _ = stopwatch.start("inner")
    _ = stopwatch.stop("inner")
    stopwatch.stop_section("inner-section")
    stopwatch.stop_section("outer-section")

    assert "inner" in stopwatch.get_section_events("inner-section")
    assert SECTION_CHILD_EVENT in stopwatch.get_section_events("outer-section")
    assert set(stopwatch.get_sections()) == {ROOT, "inner-section", "outer-section"}


def test_a_stopped_section_can_be_reopened_at_its_level(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)
    stopwatch.open_section()
    stopwatch.stop_section("one")

    stopwatch.open_section("one")
    stopwatch.stop_section("one")

    assert len(stopwatch.get_section_events("one")[SECTION_EVENT].get_periods()) == 2


def test_reopening_a_section_from_another_level_is_refused(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)

    with pytest.raises(UnknownSectionError, match='section "elsewhere"') as caught:
        stopwatch.open_section("elsewhere")

    assert caught.value.section_id == "elsewhere"


def test_stopping_with_no_section_open_is_refused(clock: MockClock) -> None:
    with pytest.raises(NoStartedSectionError) as caught:
        Stopwatch(clock).stop_section("request")

    assert caught.value.section_id == "request"


def test_stopping_an_event_that_is_not_running_is_refused(clock: MockClock) -> None:
    with pytest.raises(EventNotStartedError):
        _ = Stopwatch(clock).stop("load")


def test_a_lap_restarts_the_event(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)
    _ = stopwatch.start("load")

    _ = stopwatch.lap("load")

    assert stopwatch.is_started("load")


def test_an_unknown_section_has_no_events(clock: MockClock) -> None:
    assert Stopwatch(clock).get_section_events("missing") == {}


def test_a_reset_forgets_what_the_context_timed(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)
    stopwatch.open_section()
    stopwatch.stop_section("request")

    stopwatch.reset()

    assert stopwatch.get_section_events("request") == {}
    assert repr(stopwatch) == "Stopwatch(open_sections=0)"


def test_setting_the_detached_variable_back_forgets_what_the_context_timed(
    clock: MockClock,
) -> None:
    stopwatch = Stopwatch(clock)
    stopwatch.open_section()
    variable, value = stopwatch.detached_variable

    _ = variable.set(value)

    assert repr(stopwatch) == "Stopwatch(open_sections=0)"


def test_a_section_is_open_only_between_opening_and_stopping_it(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)
    assert not stopwatch.has_open_section()

    stopwatch.open_section()
    assert stopwatch.has_open_section()

    stopwatch.stop_section("request")
    assert not stopwatch.has_open_section()


def test_an_event_handed_out_before_a_reset_still_stops(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)
    event = stopwatch.start("listener")

    stopwatch.reset()
    _ = event.stop()

    assert len(event.get_periods()) == 1
    assert not stopwatch.is_started("listener")


def test_the_open_sections_show_in_its_repr(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)
    assert repr(stopwatch) == "Stopwatch(open_sections=0)"

    stopwatch.open_section()

    assert repr(stopwatch) == "Stopwatch(open_sections=1)"


def test_a_stopwatch_without_a_clock_still_times() -> None:
    stopwatch = Stopwatch()

    assert stopwatch.start("a").stop().get_duration() >= 0.0


@pytest.mark.anyio
async def test_concurrent_tasks_each_time_only_their_own_events(clock: MockClock) -> None:
    stopwatch = Stopwatch(clock)
    seen: dict[str, set[str]] = {}

    async def unit(name: str) -> None:
        stopwatch.reset()
        stopwatch.open_section()
        _ = stopwatch.start(name)
        await anyio.lowlevel.checkpoint()
        _ = stopwatch.stop(name)
        stopwatch.stop_section(name)
        seen[name] = set(stopwatch.get_section_events(name)) - {SECTION_EVENT}

    async with anyio.create_task_group() as group:
        _ = group.start_soon(unit, "first")
        _ = group.start_soon(unit, "second")

    assert seen == {"first": {"first"}, "second": {"second"}}
