from __future__ import annotations

import pytest
from xtr_logging_contracts import InvalidLevelError, Level

from xtr_logging.config import CapturedLoggerSpec, CaptureSpec


def test_a_bare_level_is_read_as_a_logger_spec_of_its_own() -> None:
    spec = CaptureSpec(loggers={"httpx": "info"})

    assert spec.logger_spec("httpx") == CapturedLoggerSpec(level="info")


def test_it_names_every_channel_it_routes_to() -> None:
    spec = CaptureSpec(
        channel="stdlib",
        loggers={"sqlalchemy": CapturedLoggerSpec(level=Level.WARNING, channel="db")},
    )

    assert spec.channels == ("stdlib", "db")


def test_a_logger_level_that_names_no_level_is_refused() -> None:
    with pytest.raises(InvalidLevelError):
        _ = CaptureSpec(loggers={"httpx": "loud"})
