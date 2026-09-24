from __future__ import annotations

from typing import final

import pytest
from typing_extensions import override

from tests.support.records import make_record
from xtr_logging import (
    AbstractHandler,
    EmptyStackError,
    HandlerInterface,
    Level,
    LogRecord,
    TestHandler,
)
from xtr_logging.handler.filter_handler import FilterHandler


@final
class Spy(AbstractHandler):
    """Counts the reset calls a wrapped handler receives."""

    def __init__(self) -> None:
        super().__init__()
        self.resets = 0

    @override
    def handle(self, record: LogRecord, /) -> bool:
        return False

    @override
    def reset(self) -> None:
        self.resets += 1


@final
class CountingFactory:
    """Builds one handler, lazily, and counts how often it was asked to."""

    def __init__(self, handler: HandlerInterface) -> None:
        self.handler = handler
        self.calls = 0

    def __call__(self, record: LogRecord | None, owner: FilterHandler, /) -> HandlerInterface:
        self.calls += 1
        return self.handler


def _stamp(record: LogRecord, /) -> LogRecord:
    return record.with_extra({"stamped": True})


def test_it_forwards_a_record_inside_the_band() -> None:
    member = TestHandler()
    handler = FilterHandler(member, Level.INFO, Level.WARNING)

    _ = handler.handle(make_record(Level.NOTICE))

    assert len(member.records) == 1


def test_it_drops_a_record_below_the_band() -> None:
    member = TestHandler()
    handler = FilterHandler(member, Level.INFO, Level.WARNING)

    result = handler.handle(make_record(Level.DEBUG))

    assert result is False
    assert member.records == ()


def test_it_drops_a_record_above_the_band() -> None:
    member = TestHandler()
    handler = FilterHandler(member, Level.INFO, Level.WARNING)

    _ = handler.handle(make_record(Level.ERROR))

    assert member.records == ()


def test_an_explicit_list_accepts_only_those_levels() -> None:
    member = TestHandler()
    handler = FilterHandler(member, [Level.INFO, Level.ERROR])

    for level in (Level.DEBUG, Level.INFO, Level.WARNING, Level.ERROR):
        _ = handler.handle(make_record(level))

    assert [record.level for record in member.records] == [Level.INFO, Level.ERROR]


def test_accepted_levels_reports_the_band_least_severe_first() -> None:
    handler = FilterHandler(TestHandler(), Level.INFO, Level.WARNING)

    assert handler.accepted_levels == (Level.INFO, Level.NOTICE, Level.WARNING)


def test_set_accepted_levels_changes_the_band() -> None:
    handler = FilterHandler(TestHandler(), Level.INFO, Level.WARNING)

    handler.set_accepted_levels(Level.ERROR, Level.CRITICAL)

    assert handler.accepted_levels == (Level.ERROR, Level.CRITICAL)


def test_handle_batch_forwards_only_the_accepted_records() -> None:
    member = TestHandler()
    handler = FilterHandler(member, Level.INFO, Level.WARNING)

    handler.handle_batch(
        [make_record(Level.DEBUG), make_record(Level.INFO), make_record(Level.ERROR)],
    )

    assert [record.level for record in member.records] == [Level.INFO]


def test_bubble_off_stops_an_accepted_record() -> None:
    handler = FilterHandler(TestHandler(), Level.INFO, Level.WARNING, bubble=False)

    assert handler.handle(make_record(Level.INFO))


def test_its_processors_run_before_forwarding() -> None:
    member = TestHandler()
    handler = FilterHandler(member, Level.INFO, Level.WARNING)
    handler.push_processor(_stamp)

    _ = handler.handle(make_record(Level.INFO))

    assert member.records[0].extra["stamped"] is True


def test_reset_resets_the_wrapped_handler() -> None:
    spy = Spy()
    handler = FilterHandler(spy)

    handler.reset()

    assert spy.resets == 1


def test_a_handler_factory_is_resolved_lazily() -> None:
    member = TestHandler()
    factory = CountingFactory(member)
    handler = FilterHandler(factory, Level.INFO, Level.WARNING)

    _ = handler.handle(make_record(Level.DEBUG))
    assert factory.calls == 0

    _ = handler.handle(make_record(Level.INFO))
    _ = handler.handle(make_record(Level.WARNING))

    assert factory.calls == 1
    assert len(member.records) == 2


def test_popping_with_no_processors_is_refused() -> None:
    with pytest.raises(EmptyStackError, match="FilterHandler"):
        _ = FilterHandler(TestHandler()).pop_processor()
