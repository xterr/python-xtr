from __future__ import annotations

from xtr_logging_contracts import LoggingError

from xtr_logging import UnknownHandlerError


def test_it_carries_what_it_reports() -> None:
    error = UnknownHandlerError("file", "handler main", ())

    assert (error.name, error.referenced_by, error.known) == ("file", "handler main", ())
    assert "defined: <none>" in str(error)


def test_it_is_a_logging_error() -> None:
    error = UnknownHandlerError("file", "handler main", ())

    assert isinstance(error, LoggingError)
