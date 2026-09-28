from __future__ import annotations

from xtr_logging_contracts import LoggingError

from xtr_logging import CaptureConflictError


def test_it_carries_what_it_reports() -> None:
    error = CaptureConflictError("bridge")

    assert error.handler == "bridge"
    assert "'bridge'" in str(error)


def test_it_is_a_logging_error() -> None:
    error = CaptureConflictError("bridge")

    assert isinstance(error, LoggingError)
