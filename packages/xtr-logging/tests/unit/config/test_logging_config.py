from __future__ import annotations

import pytest

from xtr_logging import InvalidLevelError, Level
from xtr_logging.config import (
    BufferHandlerSpec,
    CapturedLoggerSpec,
    CaptureSpec,
    ConsoleHandlerSpec,
    FingersCrossedHandlerSpec,
    GroupHandlerSpec,
    JsonFormatterSpec,
    LoggingConfig,
    NullHandlerSpec,
    StdlibHandlerSpec,
    StreamHandlerSpec,
    UidProcessorSpec,
)
from xtr_logging.exception.capture_conflict_error import CaptureConflictError
from xtr_logging.exception.circular_handler_reference_error import CircularHandlerReferenceError
from xtr_logging.exception.invalid_configuration_error import InvalidConfigurationError
from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.exception.mixed_channel_filter_error import MixedChannelFilterError
from xtr_logging.exception.unknown_channel_error import UnknownChannelError
from xtr_logging.exception.unknown_handler_error import UnknownHandlerError


def test_an_empty_config_has_only_the_default_channel() -> None:
    config = LoggingConfig()

    assert config.all_channels == ("app",)
    assert config.handlers == {}


def test_channels_named_by_handlers_are_declared_too() -> None:
    config = LoggingConfig(
        channels=("security",),
        handlers={"console": ConsoleHandlerSpec(channels=("!event",))},
    )

    assert config.all_channels == ("app", "security", "event")


def test_handlers_named_by_a_wrapper_leave_the_channel_stacks() -> None:
    config = LoggingConfig(
        handlers={
            "main": FingersCrossedHandlerSpec(handler="file"),
            "file": StreamHandlerSpec(path="app.log"),
            "hidden": NullHandlerSpec(nested=True),
        },
    )

    assert config.nested_handlers == frozenset({"file", "hidden"})
    assert config.top_level_handlers == ("main",)


def test_top_level_handlers_are_ordered_by_priority_then_declaration() -> None:
    config = LoggingConfig(
        handlers={
            "a": NullHandlerSpec(),
            "b": NullHandlerSpec(priority=10),
            "c": NullHandlerSpec(),
        },
    )

    assert config.top_level_handlers == ("b", "a", "c")


def test_a_wrapper_naming_a_missing_handler_is_refused() -> None:
    with pytest.raises(UnknownHandlerError) as raised:
        _ = LoggingConfig(handlers={"main": BufferHandlerSpec(handler="file")})

    assert (raised.value.name, raised.value.referenced_by) == ("file", "handler 'main'")


def test_wrappers_nesting_each_other_in_a_loop_are_refused() -> None:
    with pytest.raises(CircularHandlerReferenceError) as raised:
        _ = LoggingConfig(
            handlers={
                "a": GroupHandlerSpec(members=("b",)),
                "b": BufferHandlerSpec(handler="a"),
            },
        )

    assert raised.value.path == ("a", "b", "a")


def test_a_processor_targeting_a_missing_channel_is_refused() -> None:
    with pytest.raises(UnknownChannelError):
        _ = LoggingConfig(processors=(UidProcessorSpec(channel="nowhere"),))


def test_a_processor_targeting_a_missing_handler_is_refused() -> None:
    with pytest.raises(UnknownHandlerError):
        _ = LoggingConfig(processors=(UidProcessorSpec(handler="nowhere"),))


def test_a_processor_may_not_target_both_a_channel_and_a_handler() -> None:
    with pytest.raises(InvalidOptionError):
        _ = UidProcessorSpec(channel="app", handler="main")


def test_a_spec_refuses_an_unknown_level_where_it_is_written() -> None:
    with pytest.raises(InvalidLevelError):
        _ = StreamHandlerSpec(level="loud")


def test_a_spec_refuses_a_mixed_channel_list_where_it_is_written() -> None:
    with pytest.raises(MixedChannelFilterError):
        _ = NullHandlerSpec(channels=("a", "!b"))


def test_from_mapping_reads_tagged_handlers_and_formatters() -> None:
    config = LoggingConfig.from_mapping(
        {
            "handlers": {
                "file": {
                    "type": "stream",
                    "path": "app.log",
                    "level": "info",
                    "formatter": {"type": "json"},
                },
            },
        },
    )

    assert config.handlers["file"] == StreamHandlerSpec(
        path="app.log",
        level="info",
        formatter=JsonFormatterSpec(),
    )


def test_from_mapping_accepts_a_level_by_value() -> None:
    config = LoggingConfig.from_mapping({"handlers": {"n": {"type": "null", "level": 400}}})

    spec = config.handlers["n"]
    assert isinstance(spec, NullHandlerSpec)
    assert Level.parse(spec.level) is Level.ERROR


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        ({"handlers": {"a": {"type": "stream", "levle": "info"}}}, "unknown field `levle`"),
        ({"handlers": {"a": {"type": "stream", "level": "loud"}}}, "'loud' is not a log level"),
        ({"handlers": {"a": {"type": "carrier_pigeon"}}}, "Invalid value 'carrier_pigeon'"),
        (
            {"handlers": {"a": {"type": "sampling", "handler": "a", "factor": "3"}}},
            "Expected `int`",
        ),
        ({"chanels": []}, "unknown field `chanels`"),
    ],
)
def test_from_mapping_names_what_is_wrong(data: dict[str, object], fragment: str) -> None:
    with pytest.raises(InvalidConfigurationError, match=fragment):
        _ = LoggingConfig.from_mapping(data)


def test_a_capture_section_reads_levels_and_channels_per_logger() -> None:
    config = LoggingConfig.from_mapping(
        {
            "channels": ["db"],
            "capture": {
                "level": "error",
                "loggers": {"httpx": "info", "sqlalchemy": {"level": "warning", "channel": "db"}},
            },
        },
    )

    assert config.capture is not None
    assert config.capture.logger_spec("httpx") == CapturedLoggerSpec(level="info")
    assert config.capture.logger_spec("sqlalchemy") == CapturedLoggerSpec(
        level="warning", channel="db"
    )


def test_a_capture_naming_a_missing_channel_is_refused() -> None:
    with pytest.raises(UnknownChannelError):
        _ = LoggingConfig(
            capture=CaptureSpec(loggers={"httpx": CapturedLoggerSpec(channel="http")})
        )


def test_a_capture_refuses_an_unknown_level_with_its_path() -> None:
    with pytest.raises(InvalidConfigurationError, match=r"'loud' is not a log level"):
        _ = LoggingConfig.from_mapping({"capture": {"loggers": {"httpx": "loud"}}})


def test_capture_and_a_stdlib_handler_are_refused_together() -> None:
    with pytest.raises(CaptureConflictError) as raised:
        _ = LoggingConfig(handlers={"out": StdlibHandlerSpec()}, capture=CaptureSpec())

    assert raised.value.handler == "out"
