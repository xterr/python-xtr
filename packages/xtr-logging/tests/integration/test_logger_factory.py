"""A configuration read from TOML, built into loggers that write real files."""

from __future__ import annotations

import logging
import tomllib
from typing import TYPE_CHECKING

import msgspec
import pytest

from tests.support.stdlib import Collector
from xtr_logging import LoggerFactory, LoggingConfig, ProcessorRegistry, bound_context

if TYPE_CHECKING:
    from pathlib import Path

_CONFIG = """
channels = ["security"]

[handlers.main]
type = "fingers_crossed"
action_level = "error"
handler = "file"

[handlers.file]
type = "stream"
path = "{log}"
formatter = {{ type = "line", format = "%channel%.%level_name%: %message% %extra%\\n" }}

[handlers.audit]
type = "stream"
path = "{audit}"
channels = ["security"]
level = "notice"
formatter = {{ type = "json" }}

[[processors]]
type = "placeholder"

[[processors]]
type = "context_vars"
"""


def _factory(tmp_path: Path) -> LoggerFactory:
    text = _CONFIG.format(log=tmp_path / "app.log", audit=tmp_path / "audit.json")
    return LoggerFactory(
        LoggingConfig.from_mapping(tomllib.loads(text)), registry=ProcessorRegistry()
    )


def test_a_quiet_request_leaves_no_trace_and_a_failed_one_leaves_its_whole_story(
    tmp_path: Path,
) -> None:
    with _factory(tmp_path) as factory:
        logger = factory.logger()
        logger.info("request {id} started", {"id": 1})
        factory.reset()
        with bound_context({"request": 2}):
            logger.info("request {id} started", {"id": 2})
            logger.error("payment failed")

    lines = (tmp_path / "app.log").read_text().splitlines()
    assert lines == [
        'app.INFO: request 2 started {"request":2}',
        'app.ERROR: payment failed {"request":2}',
    ]


def test_a_channel_filtered_handler_writes_only_its_channel_as_json(tmp_path: Path) -> None:
    with _factory(tmp_path) as factory:
        factory.logger("security").notice("user {user} logged in", {"user": "ana"})
        factory.logger().notice("unrelated")

    [line] = (tmp_path / "audit.json").read_text().splitlines()
    record = msgspec.json.decode(line, type=dict[str, object])
    assert (record["channel"], record["level_name"], record["message"]) == (
        "security",
        "NOTICE",
        "user ana logged in",
    )


@pytest.mark.usefixtures("stdlib_logging")
def test_captured_stdlib_logging_joins_the_channels_and_prints_nowhere_else(tmp_path: Path) -> None:
    console = Collector()
    logging.getLogger().addHandler(console)
    text = (
        _CONFIG.format(log=tmp_path / "app.log", audit=tmp_path / "audit.json")
        + """
[capture]
level = "warning"

[capture.loggers]
"e2e.thirdparty" = "info"
"""
    )

    with LoggerFactory(
        LoggingConfig.from_mapping(tomllib.loads(text)), registry=ProcessorRegistry()
    ):
        logging.getLogger("e2e.thirdparty").info("pool opened")
        logging.getLogger("e2e.other").info("dropped by the root level")
        logging.getLogger("e2e.thirdparty").error("query failed")

    assert (tmp_path / "app.log").read_text().splitlines() == [
        "app.INFO: pool opened []",
        "app.ERROR: query failed []",
    ]
    assert console.records == []
