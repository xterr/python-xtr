from __future__ import annotations

from xtr_logging_contracts import LoggingError

from xtr_logging import InvalidOptionError


def test_it_carries_what_it_reports() -> None:
    error = InvalidOptionError("time", "-1", "must be positive")

    assert (error.option, error.value, error.reason) == ("time", "-1", "must be positive")
    assert "time=-1 is refused: must be positive" in str(error)


def test_it_is_a_logging_error() -> None:
    error = InvalidOptionError("time", "-1", "must be positive")

    assert isinstance(error, LoggingError)
    assert isinstance(error, ValueError)
