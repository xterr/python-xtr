"""Logging described as data.

A :class:`LoggingConfig` names channels, handlers and processors, and a
:class:`~xtr_logging.logger_factory.LoggerFactory` builds loggers from it.
"""

from __future__ import annotations

from .capture_config import CaptureConfig, CapturedLoggerConfig
from .channel_filter import ChannelFilter
from .formatter_configs import (
    ConsoleFormatterConfig,
    FormatterConfig,
    JsonFormatterConfig,
    LineFormatterConfig,
)
from .handler_configs import (
    BaseHandlerConfig,
    ConsoleHandlerConfig,
    FormattedHandlerConfig,
    NullHandlerConfig,
    RotatingFileHandlerConfig,
    ServiceHandlerConfig,
    StdlibHandlerConfig,
    StreamHandlerConfig,
    SyslogHandlerConfig,
)
from .logging_config import HandlerConfig, LoggingConfig
from .processor_configs import (
    ContextVarsProcessorConfig,
    HostnameProcessorConfig,
    IntrospectionProcessorConfig,
    PlaceholderProcessorConfig,
    ProcessIdProcessorConfig,
    ProcessorConfig,
    ServiceProcessorConfig,
    TagProcessorConfig,
    UidProcessorConfig,
)
from .services import Services
from .wrapper_handler_configs import (
    BufferHandlerConfig,
    DeduplicationHandlerConfig,
    FallbackGroupHandlerConfig,
    FilterHandlerConfig,
    FingersCrossedHandlerConfig,
    GroupHandlerConfig,
    QueueHandlerConfig,
    SamplingHandlerConfig,
    WhatFailureGroupHandlerConfig,
)

__all__ = [
    "BaseHandlerConfig",
    "BufferHandlerConfig",
    "CaptureConfig",
    "CapturedLoggerConfig",
    "ChannelFilter",
    "ConsoleFormatterConfig",
    "ConsoleHandlerConfig",
    "ContextVarsProcessorConfig",
    "DeduplicationHandlerConfig",
    "FallbackGroupHandlerConfig",
    "FilterHandlerConfig",
    "FingersCrossedHandlerConfig",
    "FormattedHandlerConfig",
    "FormatterConfig",
    "GroupHandlerConfig",
    "HandlerConfig",
    "HostnameProcessorConfig",
    "IntrospectionProcessorConfig",
    "JsonFormatterConfig",
    "LineFormatterConfig",
    "LoggingConfig",
    "NullHandlerConfig",
    "PlaceholderProcessorConfig",
    "ProcessIdProcessorConfig",
    "ProcessorConfig",
    "QueueHandlerConfig",
    "RotatingFileHandlerConfig",
    "SamplingHandlerConfig",
    "ServiceHandlerConfig",
    "ServiceProcessorConfig",
    "Services",
    "StdlibHandlerConfig",
    "StreamHandlerConfig",
    "SyslogHandlerConfig",
    "TagProcessorConfig",
    "UidProcessorConfig",
    "WhatFailureGroupHandlerConfig",
]
