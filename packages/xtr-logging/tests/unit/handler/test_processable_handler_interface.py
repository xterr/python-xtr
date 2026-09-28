from __future__ import annotations

from xtr_logging import NullHandler, TestHandler
from xtr_logging.handler.processable_handler_interface import ProcessableHandlerInterface


def test_a_handler_that_runs_processors_satisfies_it() -> None:
    assert isinstance(TestHandler(), ProcessableHandlerInterface)


def test_a_handler_that_writes_nothing_does_not() -> None:
    assert not isinstance(NullHandler(), ProcessableHandlerInterface)
