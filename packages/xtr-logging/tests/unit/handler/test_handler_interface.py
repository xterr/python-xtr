from __future__ import annotations

from xtr_logging import NullHandler, TestHandler
from xtr_logging.handler.handler_interface import HandlerInterface


def test_the_shipped_handlers_satisfy_it() -> None:
    assert isinstance(NullHandler(), HandlerInterface)
    assert isinstance(TestHandler(), HandlerInterface)


def test_an_unrelated_object_does_not() -> None:
    assert not isinstance(object(), HandlerInterface)
