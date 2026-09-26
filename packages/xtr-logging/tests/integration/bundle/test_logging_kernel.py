"""End-to-end: an application listing only LoggingBundle gets qualified channel loggers."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_logging_contracts import LoggerInterface

from tests.fixtures.app_logging.config import HANDLER

pytestmark = pytest.mark.anyio


async def test_the_app_logs_through_each_channel() -> None:
    kernel = Kernel("tests.fixtures.app_logging", env="test")
    booted = await kernel.boot()
    try:
        default_logger = await booted.container.get(LoggerInterface)
        security_logger = await booted.container.get(LoggerInterface, "security")
        default_logger.warning("default line")
        security_logger.notice("security line")
    finally:
        await booted.shutdown()

    seen = {(record.channel, record.message) for record in HANDLER.records}
    assert ("app", "default line") in seen
    assert ("security", "security line") in seen
