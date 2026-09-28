from __future__ import annotations

from xtr_logging_contracts import LoggingError

from xtr_logging import EmptyStackError


def test_it_carries_what_it_reports() -> None:
    error = EmptyStackError("Logger app", "handler")

    assert (error.owner, error.stack) == ("Logger app", "handler")
    assert "empty handler stack of Logger app" in str(error)


def test_it_is_a_logging_error() -> None:
    error = EmptyStackError("Logger app", "handler")

    assert isinstance(error, LoggingError)
