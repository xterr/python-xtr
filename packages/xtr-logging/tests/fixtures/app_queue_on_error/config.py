"""A queue handler whose ``on_error`` names an error-handler service the app registers."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import as_service, configure

from xtr_logging import AbstractHandler, ErrorHandlerInterface, LogRecord
from xtr_logging.bundle import LoggingConfig
from xtr_logging.config import QueueHandlerConfig, ServiceHandlerConfig
from xtr_logging.handler.handler_interface import HandlerInterface

REPORTED: list[str] = []


@final
class Failing(AbstractHandler):
    """Fails on every record, so the queue handler has something to report."""

    @override
    def handle(self, record: LogRecord, /) -> bool:
        raise RuntimeError(record.message)


def _collect(error: Exception, record: LogRecord) -> None:
    REPORTED.append(f"{error}:{record.message}")


@configure
def logging_config() -> LoggingConfig:
    """Queue every record onto a failing handler, reporting to ``collect``."""
    return LoggingConfig(
        handlers={
            "queued": QueueHandlerConfig(handler="failing", on_error="collect"),
            "failing": ServiceHandlerConfig(id="failing"),
        },
    )


@as_service(qualifier="failing")
def failing_handler() -> HandlerInterface:
    """Provide the failing handler under the id the config names."""
    return Failing()


@as_service(qualifier="collect")
def collect() -> ErrorHandlerInterface:
    """Provide the error handler under the id ``on_error`` names."""
    return _collect
