from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from tests.support.records import make_record
from xtr_logging import AbstractHandler, EmptyStackError, Level, LogRecord, TestHandler
from xtr_logging.handler.group_handler import GroupHandler

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
class Spy(AbstractHandler):
    """Counts the lifecycle calls a member receives."""

    def __init__(self) -> None:
        super().__init__()
        self.closed = 0
        self.resets = 0

    @override
    def handle(self, record: LogRecord, /) -> bool:
        return False

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        pass

    @override
    def close(self) -> None:
        self.closed += 1

    @override
    def reset(self) -> None:
        self.resets += 1


def _stamp(record: LogRecord, /) -> LogRecord:
    return record.with_extra({"stamped": True})


def test_it_forwards_a_record_to_every_member() -> None:
    first, second = TestHandler(), TestHandler()
    group = GroupHandler([first, second])

    _ = group.handle(make_record(message="hi"))

    assert len(first.records) == len(second.records) == 1


def test_is_handling_is_true_when_any_member_would_handle() -> None:
    group = GroupHandler([TestHandler(Level.ERROR), TestHandler(Level.DEBUG)])

    assert group.is_handling(make_record(Level.INFO))


def test_is_handling_is_false_when_no_member_would_handle() -> None:
    group = GroupHandler([TestHandler(Level.ERROR)])

    assert not group.is_handling(make_record(Level.INFO))


def test_handle_batch_forwards_the_batch_to_every_member() -> None:
    first, second = TestHandler(), TestHandler()
    group = GroupHandler([first, second])

    group.handle_batch([make_record(message="a"), make_record(message="b")])

    assert [record.message for record in first.records] == ["a", "b"]
    assert [record.message for record in second.records] == ["a", "b"]


def test_close_closes_every_member() -> None:
    first, second = Spy(), Spy()
    group = GroupHandler([first, second])

    group.close()

    assert (first.closed, second.closed) == (1, 1)


def test_reset_resets_every_member() -> None:
    first, second = Spy(), Spy()
    group = GroupHandler([first, second])

    group.reset()

    assert (first.resets, second.resets) == (1, 1)


def test_bubble_off_stops_the_record() -> None:
    assert GroupHandler([TestHandler()], bubble=False).handle(make_record())


def test_a_bubbling_group_does_not_stop_the_record() -> None:
    assert not GroupHandler([TestHandler()]).handle(make_record())


def test_its_processors_run_before_forwarding() -> None:
    member = TestHandler()
    group = GroupHandler([member])
    group.push_processor(_stamp)

    _ = group.handle(make_record())

    assert member.records[0].extra["stamped"] is True


def test_popping_with_no_processors_is_refused() -> None:
    with pytest.raises(EmptyStackError, match="GroupHandler"):
        _ = GroupHandler([TestHandler()]).pop_processor()
