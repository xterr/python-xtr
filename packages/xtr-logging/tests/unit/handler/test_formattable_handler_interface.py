from __future__ import annotations

from xtr_logging import NullHandler, TestHandler
from xtr_logging.handler.formattable_handler_interface import FormattableHandlerInterface


def test_a_handler_that_formats_satisfies_it() -> None:
    assert isinstance(TestHandler(), FormattableHandlerInterface)


def test_a_handler_that_writes_nothing_does_not() -> None:
    assert not isinstance(NullHandler(), FormattableHandlerInterface)
