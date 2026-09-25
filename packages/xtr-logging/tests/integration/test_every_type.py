"""Every handler, formatter and processor type builds from data, into the right class."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import pytest

from xtr_logging import (
    BufferHandler,
    ConsoleHandler,
    DeduplicationHandler,
    FallbackGroupHandler,
    FilterHandler,
    FingersCrossedHandler,
    FormattableHandlerInterface,
    GroupHandler,
    JsonFormatter,
    LineFormatter,
    LoggerFactory,
    LoggingConfig,
    NullHandler,
    ProcessorRegistry,
    QueueHandler,
    RotatingFileHandler,
    SamplingHandler,
    StreamHandler,
    SyslogHandler,
    WhatFailureGroupHandler,
)
from xtr_logging.bridge.stdlib import StdlibHandler
from xtr_logging.exception import InvalidOptionError, UnknownServiceError
from xtr_logging.formatter import ConsoleFormatter

if TYPE_CHECKING:
    from pathlib import Path

_EVERY_TYPE = """
[handlers.stream]
type = "stream"
path = "{dir}/stream.log"
formatter = {{ type = "line", format = "%message%" }}

[handlers.rotating]
type = "rotating_file"
path = "{dir}/rotating.log"
max_files = 3
formatter = {{ type = "json", batch_mode = "newlines" }}

[handlers.syslog]
type = "syslog"
address = "127.0.0.1:5140"
nested = true

[handlers.console]
type = "console"
stream = "stdout"
verbosity_levels = {{ quiet = "critical" }}
formatter = {{ type = "console", colors = true }}

[handlers.null]
type = "null"
level = "debug"
nested = true

[handlers.stdlib]
type = "stdlib"
logger = "every.type"
nested = true

[handlers.crossed]
type = "fingers_crossed"
handler = "stream"
channel_levels = {{ app = "error" }}
passthru_level = "notice"

[handlers.buffer]
type = "buffer"
handler = "null"
buffer_size = 10

[handlers.filter]
type = "filter"
handler = "stdlib"
accepted_levels = ["error", "critical"]

[handlers.dedup]
type = "deduplication"
handler = "rotating"
store = "{dir}/dedup.store"

[handlers.sampling]
type = "sampling"
handler = "syslog"
factor = 10

[handlers.queue]
type = "queue"
handler = "buffer"

[handlers.group]
type = "group"
members = ["crossed", "filter"]

[handlers.whatfailure]
type = "whatfailuregroup"
members = ["dedup"]

[handlers.fallback]
type = "fallbackgroup"
members = ["sampling", "queue"]

[[processors]]
type = "placeholder"
[[processors]]
type = "uid"
length = 12
[[processors]]
type = "hostname"
[[processors]]
type = "process_id"
[[processors]]
type = "introspection"
level = "error"
[[processors]]
type = "tags"
tags = ["web"]
[[processors]]
type = "context_vars"
key = "ctx"
"""


def _factory(tmp_path: Path) -> LoggerFactory:
    config = LoggingConfig.from_mapping(tomllib.loads(_EVERY_TYPE.format(dir=tmp_path)))
    return LoggerFactory(config, registry=ProcessorRegistry())


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("stream", StreamHandler),
        ("rotating", RotatingFileHandler),
        ("syslog", SyslogHandler),
        ("console", ConsoleHandler),
        ("null", NullHandler),
        ("stdlib", StdlibHandler),
        ("crossed", FingersCrossedHandler),
        ("buffer", BufferHandler),
        ("filter", FilterHandler),
        ("dedup", DeduplicationHandler),
        ("sampling", SamplingHandler),
        ("queue", QueueHandler),
        ("group", GroupHandler),
        ("whatfailure", WhatFailureGroupHandler),
        ("fallback", FallbackGroupHandler),
    ],
)
def test_each_handler_type_builds_its_class(tmp_path: Path, name: str, expected: type) -> None:
    with _factory(tmp_path) as factory:
        assert isinstance(factory.handler(name), expected)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("stream", LineFormatter), ("rotating", JsonFormatter), ("console", ConsoleFormatter)],
)
def test_each_formatter_type_is_set_on_its_handler(
    tmp_path: Path, name: str, expected: type
) -> None:
    with _factory(tmp_path) as factory:
        handler = factory.handler(name)
        assert isinstance(handler, FormattableHandlerInterface)
        assert isinstance(handler.formatter, expected)


def test_every_processor_type_runs_on_a_record(tmp_path: Path) -> None:
    with _factory(tmp_path) as factory:
        logger = factory.logger()
        logger.info("x")
        assert len(logger.processors) == 7


def test_a_formatter_named_by_id_must_be_supplied() -> None:
    config = LoggingConfig.from_mapping(
        {"handlers": {"s": {"type": "stream", "formatter": "mine"}}}
    )

    with pytest.raises(UnknownServiceError):
        _ = LoggerFactory(config, registry=ProcessorRegistry())


def test_an_unusable_syslog_address_is_refused() -> None:
    config = LoggingConfig.from_mapping(
        {"handlers": {"s": {"type": "syslog", "address": "nowhere"}}}
    )

    with pytest.raises(InvalidOptionError):
        _ = LoggerFactory(config, registry=ProcessorRegistry())


@pytest.mark.parametrize("name", ["loud", "silent"])
def test_an_unknown_or_unmappable_verbosity_is_refused(name: str) -> None:
    config = LoggingConfig.from_mapping(
        {"handlers": {"c": {"type": "console", "verbosity_levels": {name: "debug"}}}},
    )

    with pytest.raises(InvalidOptionError):
        _ = LoggerFactory(config, registry=ProcessorRegistry())
