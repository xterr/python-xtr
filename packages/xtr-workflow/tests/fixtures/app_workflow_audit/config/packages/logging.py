"""Every record lands in a test handler the tests read back."""

from __future__ import annotations

from xtr_dependency_injection import as_service, configure
from xtr_logging import HandlerInterface, LoggingConfig, TestHandler
from xtr_logging.config import ServiceHandlerConfig

CAPTURED: list[TestHandler] = []
"""Every capture handler built, newest last."""


@configure
def logging_config() -> LoggingConfig:
    return LoggingConfig(handlers={"capture": ServiceHandlerConfig(id="capture")})


@as_service(qualifier="capture")
def capture_handler() -> HandlerInterface:
    handler = TestHandler()
    CAPTURED.append(handler)
    return handler
