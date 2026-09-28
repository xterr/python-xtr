from __future__ import annotations

from xtr_logging_contracts import LoggingError

from xtr_logging import MixedChannelFilterError


def test_it_carries_what_it_reports() -> None:
    error = MixedChannelFilterError(("app", "!event"))

    assert error.channels == ("app", "!event")
    assert "mix included and excluded" in str(error)


def test_it_is_a_logging_error() -> None:
    error = MixedChannelFilterError(("app", "!event"))

    assert isinstance(error, LoggingError)
    assert isinstance(error, ValueError)
