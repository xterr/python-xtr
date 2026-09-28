from __future__ import annotations

from xtr_logging_contracts import LoggingError

from xtr_logging import UnknownServiceError


def test_it_carries_what_it_reports() -> None:
    error = UnknownServiceError("handler", "sentry", ("main",))

    assert (error.kind, error.service_id, error.known) == ("handler", "sentry", ("main",))
    assert "supplied: main" in str(error)


def test_it_is_a_logging_error() -> None:
    error = UnknownServiceError("handler", "sentry", ("main",))

    assert isinstance(error, LoggingError)
