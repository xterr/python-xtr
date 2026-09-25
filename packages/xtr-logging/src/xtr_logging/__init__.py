"""Channels, handlers, processors and formatters, behind one logger interface.

Code logs through :class:`LoggerInterface`. A :class:`Logger` is one channel:
it turns each call into an immutable :class:`LogRecord`, runs its processors,
and offers the record to a stack of handlers, which format it and write it
somewhere — stopping where a handler does not let it bubble.

:class:`LoggingConfig` describes channels, handlers and processors as data,
and :class:`LoggerFactory` builds loggers from it. The
per-type specs live in :mod:`xtr_logging.config`; the standard-library bridge
in :mod:`xtr_logging.bridge.stdlib`.

The contract itself — :class:`LoggerInterface`, :class:`Level`,
:class:`NullLogger` and what else a caller needs to log — lives in
``xtr-logging-contracts``, so a library can depend on it without depending on
any of this. It is re-exported here, never redefined: ``xtr_logging.X`` and
``xtr_logging_contracts.X`` are the same object, which is what lets a container
register a logger under the interface and have a library that never imported
this package receive it.
"""

from importlib.metadata import PackageNotFoundError, version

from .config import LoggingConfig, Services
from .decorator import as_processor
from .exception import (
    CaptureConflictError,
    CircularHandlerReferenceError,
    EmptyStackError,
    InvalidConfigurationError,
    InvalidOptionError,
    MixedChannelFilterError,
    NotProcessableHandlerError,
    UnknownChannelError,
    UnknownHandlerError,
    UnknownServiceError,
)
from .formatter import (
    ConsoleFormatter,
    FormatterInterface,
    JsonBatchMode,
    JsonFormatter,
    LineFormatter,
    Normalized,
    Normalizer,
)
from .handler import (
    AbstractHandler,
    AbstractProcessingHandler,
    ActivationStrategyInterface,
    BufferHandler,
    ChannelLevelActivationStrategy,
    ConsoleHandler,
    DeduplicationHandler,
    ErrorLevelActivationStrategy,
    FallbackGroupHandler,
    FilterHandler,
    FingersCrossedHandler,
    FormattableHandlerInterface,
    GroupHandler,
    HandlerInterface,
    NullHandler,
    ProcessableHandlerInterface,
    QueueHandler,
    RotatingFileHandler,
    SamplingHandler,
    StreamHandler,
    SyslogHandler,
    TestHandler,
    WhatFailureGroupHandler,
)
from .log_context import bind_context, bound_context, clear_context, current_context, unbind_context
from .log_record import LogRecord
from .logger import Logger
from .logger_factory import LoggerFactory
from .processor import (
    ContextVarsProcessor,
    HostnameProcessor,
    IntrospectionProcessor,
    PlaceholderProcessor,
    ProcessIdProcessor,
    ProcessorInterface,
    ProcessorRegistry,
    TagProcessor,
    UidProcessor,
    default_processor_registry,
)
from .verbosity import Verbosity

try:
    __version__ = version("xtr-logging")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "AbstractHandler",
    "AbstractProcessingHandler",
    "ActivationStrategyInterface",
    "BufferHandler",
    "CaptureConflictError",
    "ChannelLevelActivationStrategy",
    "CircularHandlerReferenceError",
    "ConsoleFormatter",
    "ConsoleHandler",
    "ContextVarsProcessor",
    "DeduplicationHandler",
    "EmptyStackError",
    "ErrorLevelActivationStrategy",
    "FallbackGroupHandler",
    "FilterHandler",
    "FingersCrossedHandler",
    "FormattableHandlerInterface",
    "FormatterInterface",
    "GroupHandler",
    "HandlerInterface",
    "HostnameProcessor",
    "IntrospectionProcessor",
    "InvalidConfigurationError",
    "InvalidOptionError",
    "JsonBatchMode",
    "JsonFormatter",
    "LineFormatter",
    "LogRecord",
    "Logger",
    "LoggerFactory",
    "LoggingConfig",
    "MixedChannelFilterError",
    "Normalized",
    "Normalizer",
    "NotProcessableHandlerError",
    "NullHandler",
    "PlaceholderProcessor",
    "ProcessIdProcessor",
    "ProcessableHandlerInterface",
    "ProcessorInterface",
    "ProcessorRegistry",
    "QueueHandler",
    "RotatingFileHandler",
    "SamplingHandler",
    "Services",
    "StreamHandler",
    "SyslogHandler",
    "TagProcessor",
    "TestHandler",
    "UidProcessor",
    "UnknownChannelError",
    "UnknownHandlerError",
    "UnknownServiceError",
    "Verbosity",
    "WhatFailureGroupHandler",
    "__version__",
    "as_processor",
    "bind_context",
    "bound_context",
    "clear_context",
    "current_context",
    "default_processor_registry",
    "unbind_context",
]
