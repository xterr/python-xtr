"""Logging described as data.

A :class:`LoggingConfig` names channels, handlers and processors, and a
:class:`~xtr_logging.logger_factory.LoggerFactory` builds loggers from it.
"""

from .capture_spec import CapturedLoggerSpec, CaptureSpec
from .channel_filter import ChannelFilter
from .formatter_specs import (
    ConsoleFormatterSpec,
    FormatterSpec,
    JsonFormatterSpec,
    LineFormatterSpec,
)
from .handler_specs import (
    BaseHandlerSpec,
    ConsoleHandlerSpec,
    FormattedHandlerSpec,
    NullHandlerSpec,
    RotatingFileHandlerSpec,
    ServiceHandlerSpec,
    StdlibHandlerSpec,
    StreamHandlerSpec,
    SyslogHandlerSpec,
)
from .logging_config import HandlerSpec, LoggingConfig
from .processor_specs import (
    ContextVarsProcessorSpec,
    HostnameProcessorSpec,
    IntrospectionProcessorSpec,
    PlaceholderProcessorSpec,
    ProcessIdProcessorSpec,
    ProcessorSpec,
    ServiceProcessorSpec,
    TagProcessorSpec,
    UidProcessorSpec,
)
from .services import Services
from .wrapper_handler_specs import (
    BufferHandlerSpec,
    DeduplicationHandlerSpec,
    FallbackGroupHandlerSpec,
    FilterHandlerSpec,
    FingersCrossedHandlerSpec,
    GroupHandlerSpec,
    QueueHandlerSpec,
    SamplingHandlerSpec,
    WhatFailureGroupHandlerSpec,
)

__all__ = [
    "BaseHandlerSpec",
    "BufferHandlerSpec",
    "CaptureSpec",
    "CapturedLoggerSpec",
    "ChannelFilter",
    "ConsoleFormatterSpec",
    "ConsoleHandlerSpec",
    "ContextVarsProcessorSpec",
    "DeduplicationHandlerSpec",
    "FallbackGroupHandlerSpec",
    "FilterHandlerSpec",
    "FingersCrossedHandlerSpec",
    "FormattedHandlerSpec",
    "FormatterSpec",
    "GroupHandlerSpec",
    "HandlerSpec",
    "HostnameProcessorSpec",
    "IntrospectionProcessorSpec",
    "JsonFormatterSpec",
    "LineFormatterSpec",
    "LoggingConfig",
    "NullHandlerSpec",
    "PlaceholderProcessorSpec",
    "ProcessIdProcessorSpec",
    "ProcessorSpec",
    "QueueHandlerSpec",
    "RotatingFileHandlerSpec",
    "SamplingHandlerSpec",
    "ServiceHandlerSpec",
    "ServiceProcessorSpec",
    "Services",
    "StdlibHandlerSpec",
    "StreamHandlerSpec",
    "SyslogHandlerSpec",
    "TagProcessorSpec",
    "UidProcessorSpec",
    "WhatFailureGroupHandlerSpec",
]
