"""A logging config naming a service id that the app never registers."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_logging.bundle import LoggingConfig
from xtr_logging.config import ServiceHandlerSpec


@configure
def logging_config() -> LoggingConfig:
    """Name a handler ``nope`` on purpose: the bundle must refuse to build."""
    return LoggingConfig(handlers={"main": ServiceHandlerSpec(id="nope")})
