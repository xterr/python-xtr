from __future__ import annotations

from xtr_logging_contracts import LoggingError

from xtr_logging import NotProcessableHandlerError


def test_it_carries_what_it_reports() -> None:
    error = NotProcessableHandlerError("sentry")

    assert error.handler == "sentry"
    assert "'sentry' runs no processors" in str(error)


def test_it_is_a_logging_error() -> None:
    error = NotProcessableHandlerError("sentry")

    assert isinstance(error, LoggingError)
