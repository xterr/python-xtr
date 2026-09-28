from __future__ import annotations

from xtr_logging_contracts import LoggingError

from xtr_logging import CircularHandlerReferenceError


def test_it_carries_what_it_reports() -> None:
    error = CircularHandlerReferenceError(("a", "b", "a"))

    assert error.path == ("a", "b", "a")
    assert "a -> b -> a" in str(error)


def test_it_is_a_logging_error() -> None:
    error = CircularHandlerReferenceError(("a", "b", "a"))

    assert isinstance(error, LoggingError)
