from __future__ import annotations

import msgspec
import pytest

from xtr_logging.config import (
    JsonFormatterConfig,
    LineFormatterConfig,
    LoggingConfig,
    StreamHandlerConfig,
)


def test_a_json_batch_defaults_to_one_object_per_line() -> None:
    assert JsonFormatterConfig().batch_mode == "newlines"


def test_the_type_tag_picks_the_formatter() -> None:
    config = LoggingConfig.from_mapping(
        {
            "handlers": {
                "main": {"type": "stream", "formatter": {"type": "line", "format": "%message%"}}
            }
        }
    )

    handler = config.handlers["main"]
    assert isinstance(handler, StreamHandlerConfig)
    assert handler.formatter == LineFormatterConfig(format="%message%")


def test_an_unknown_key_is_refused() -> None:
    with pytest.raises(msgspec.ValidationError):
        _ = msgspec.convert({"type": "json", "colour": True}, JsonFormatterConfig)
