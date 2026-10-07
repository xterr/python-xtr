from __future__ import annotations

import msgspec
import pytest

from xtr_logging.config import (
    ConsoleFormatterConfig,
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


def test_every_formatter_config_exposes_the_normalizer_limits() -> None:
    line = LineFormatterConfig(max_depth=3, max_items=7)
    json = JsonFormatterConfig(max_depth=3, max_items=7)

    assert (line.max_depth, line.max_items) == (3, 7)
    assert (json.max_depth, json.max_items) == (3, 7)


def test_a_console_formatter_config_carries_the_line_options() -> None:
    config = ConsoleFormatterConfig(
        allow_inline_line_breaks=True, ignore_empty_context_and_extra=False
    )

    assert config.allow_inline_line_breaks is True
    assert config.ignore_empty_context_and_extra is False
