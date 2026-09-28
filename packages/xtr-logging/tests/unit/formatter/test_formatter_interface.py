from __future__ import annotations

from xtr_logging import JsonFormatter, LineFormatter
from xtr_logging.formatter.formatter_interface import FormatterInterface


def test_the_shipped_formatters_satisfy_it() -> None:
    assert isinstance(LineFormatter(), FormatterInterface)
    assert isinstance(JsonFormatter(), FormatterInterface)


def test_an_unrelated_object_does_not() -> None:
    assert not isinstance(object(), FormatterInterface)
