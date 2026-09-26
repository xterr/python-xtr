"""The xtr-dependency-injection bundle for xtr-logging."""

from __future__ import annotations

from xtr_logging.config.logging_config import LoggingConfig

from .logging_bundle import LoggingBundle

__all__ = ["LoggingBundle", "LoggingConfig"]
