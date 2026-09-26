from __future__ import annotations

from typing import final

import pytest
from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import (
    EmptyStackError,
    FormattableHandlerInterface,
    LineFormatter,
    LogRecord,
    ProcessableHandlerInterface,
    TestHandler,
)


@final
class UidProcessor:
    def __init__(self) -> None:
        self.resets = 0

    def __call__(self, record: LogRecord, /) -> LogRecord:
        return record.with_extra({"uid": "abc"})

    def reset(self) -> None:
        self.resets += 1


def test_it_satisfies_both_optional_contracts() -> None:
    handler = TestHandler()

    assert isinstance(handler, ProcessableHandlerInterface)
    assert isinstance(handler, FormattableHandlerInterface)


def test_its_processors_run_before_writing() -> None:
    handler = TestHandler()
    handler.push_processor(UidProcessor())

    _ = handler.handle(make_record())

    assert handler.records[0].extra["uid"] == "abc"


def test_a_replaced_formatter_renders_the_output() -> None:
    handler = TestHandler()
    handler.formatter = LineFormatter("%level_name%|%message%")

    _ = handler.handle(make_record(Level.NOTICE, "hi"))

    assert handler.formatted == ("NOTICE|hi",)


def test_handle_returns_true_only_when_it_stops_bubbling() -> None:
    assert TestHandler(bubble=False).handle(make_record())
    assert not TestHandler().handle(make_record())


def test_a_record_below_the_level_is_neither_written_nor_stopped() -> None:
    handler = TestHandler(Level.ERROR, bubble=False)

    assert not handler.handle(make_record(Level.INFO))
    assert handler.records == ()


def test_handle_batch_writes_each_record() -> None:
    handler = TestHandler()

    handler.handle_batch([make_record(message="a"), make_record(message="b")])

    assert [r.message for r in handler.records] == ["a", "b"]


def test_reset_reaches_processors_implementing_reset_interface() -> None:
    processor = UidProcessor()
    handler = TestHandler()
    handler.push_processor(processor)

    handler.reset()

    assert processor.resets == 1


def test_popping_with_no_processors_is_refused() -> None:
    with pytest.raises(EmptyStackError, match="TestHandler"):
        _ = TestHandler().pop_processor()


def test_set_level_changes_the_threshold() -> None:
    handler = TestHandler()

    handler.set_level("error")

    assert handler.level is Level.ERROR
    assert not handler.is_handling(make_record(Level.WARNING))
