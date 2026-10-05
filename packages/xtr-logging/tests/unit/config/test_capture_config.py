from __future__ import annotations

import pytest
from xtr_logging_contracts import InvalidLevelError, Level

from xtr_logging.config import CaptureConfig, CapturedLoggerConfig


def test_a_bare_level_is_read_as_a_logger_config_of_its_own() -> None:
    capture = CaptureConfig(loggers={"httpx": "info"})

    assert capture.logger_config("httpx") == CapturedLoggerConfig(level="info")


def test_it_names_every_channel_it_routes_to() -> None:
    capture = CaptureConfig(
        channel="stdlib",
        loggers={"sqlalchemy": CapturedLoggerConfig(level=Level.WARNING, channel="db")},
    )

    assert capture.channels == ("stdlib", "db")


def test_a_logger_level_that_names_no_level_is_refused() -> None:
    with pytest.raises(InvalidLevelError):
        _ = CaptureConfig(loggers={"httpx": "loud"})
