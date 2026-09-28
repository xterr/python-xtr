from __future__ import annotations

from xtr_logging_contracts import LoggingError

from xtr_logging import UnknownChannelError


def test_it_carries_what_it_reports() -> None:
    error = UnknownChannelError("billing", ("app", "security"))

    assert (error.channel, error.known) == ("billing", ("app", "security"))
    assert "declared: app, security" in str(error)


def test_it_is_a_logging_error() -> None:
    error = UnknownChannelError("billing", ("app", "security"))

    assert isinstance(error, LoggingError)
