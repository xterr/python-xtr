"""The application's logging configuration and the handler service it names."""

from __future__ import annotations

from xtr_dependency_injection import as_service, configure

from xtr_logging import TestHandler
from xtr_logging.bundle import LoggingConfig
from xtr_logging.config import ServiceHandlerSpec
from xtr_logging.handler.handler_interface import HandlerInterface

HANDLER = TestHandler()


@configure
def logging_config() -> LoggingConfig:
    """Wire one channel besides the default, served by an in-memory handler."""
    return LoggingConfig(
        channels=("security",),
        handlers={"main": ServiceHandlerSpec(id="main")},
    )


@as_service(qualifier="main")
def main_handler() -> HandlerInterface:
    """Provide the shared :class:`TestHandler` under the id the config names."""
    return HANDLER
