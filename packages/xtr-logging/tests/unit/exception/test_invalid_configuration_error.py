from __future__ import annotations

from xtr_logging_contracts import LoggingError

from xtr_logging import InvalidConfigurationError


def test_it_carries_what_it_reports() -> None:
    error = InvalidConfigurationError("$.handlers.main: unknown key")

    assert error.detail == "$.handlers.main: unknown key"
    assert "$.handlers.main: unknown key" in str(error)


def test_it_is_a_logging_error() -> None:
    error = InvalidConfigurationError("$.handlers.main: unknown key")

    assert isinstance(error, LoggingError)
