from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from tests.support.records import make_record
from xtr_logging import AbstractHandler, LogRecord, TestHandler
from xtr_logging.handler.what_failure_group_handler import WhatFailureGroupHandler

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
class Boom(AbstractHandler):
    """A member that fails at whatever it is asked to do."""

    @override
    def handle(self, record: LogRecord, /) -> bool:
        raise RuntimeError("boom")

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        raise RuntimeError("boom batch")

    @override
    def close(self) -> None:
        raise RuntimeError("boom close")


@final
class Spy(AbstractHandler):
    """Counts the lifecycle calls a member receives."""

    def __init__(self) -> None:
        super().__init__()
        self.closed = 0

    @override
    def handle(self, record: LogRecord, /) -> bool:
        return False

    @override
    def close(self) -> None:
        self.closed += 1


def test_a_failing_member_does_not_stop_the_others() -> None:
    survivor = TestHandler()
    group = WhatFailureGroupHandler([Boom(), survivor])

    _ = group.handle(make_record(message="hi"))

    assert len(survivor.records) == 1


def test_handle_batch_survives_a_failing_member() -> None:
    survivor = TestHandler()
    group = WhatFailureGroupHandler([Boom(), survivor])

    group.handle_batch([make_record(message="a"), make_record(message="b")])

    assert [record.message for record in survivor.records] == ["a", "b"]


def test_close_survives_a_failing_member() -> None:
    survivor = Spy()
    group = WhatFailureGroupHandler([Boom(), survivor])

    group.close()

    assert survivor.closed == 1


def test_it_returns_true_when_bubble_is_off() -> None:
    assert WhatFailureGroupHandler([TestHandler()], bubble=False).handle(make_record())
