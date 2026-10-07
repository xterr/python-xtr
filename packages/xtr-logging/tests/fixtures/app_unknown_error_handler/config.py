"""A queue handler whose ``on_error`` names a service the app never registers."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_logging.bundle import LoggingConfig
from xtr_logging.config import NullHandlerConfig, QueueHandlerConfig


@configure
def logging_config() -> LoggingConfig:
    """Name an error handler ``nope`` on purpose: the bundle must refuse to build."""
    return LoggingConfig(
        handlers={
            "queued": QueueHandlerConfig(handler="null", on_error="nope"),
            "null": NullHandlerConfig(),
        },
    )
