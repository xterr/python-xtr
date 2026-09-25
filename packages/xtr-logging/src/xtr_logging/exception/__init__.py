"""Every error this library raises.

All of them derive from :class:`LoggingError`, so one ``except`` catches
anything logging can go wrong with, and a narrower one handles a single
cause. Each carries the data a caller needs as typed attributes rather than
forcing a message to be parsed.

:class:`LoggingError` and :class:`InvalidLevelError` belong to the contract
rather than to this library, and are re-exported here so one ``except`` still
reaches both halves.
"""

from xtr_logging_contracts import InvalidLevelError, LoggingError

from .capture_conflict_error import CaptureConflictError
from .circular_handler_reference_error import CircularHandlerReferenceError
from .empty_stack_error import EmptyStackError
from .invalid_configuration_error import InvalidConfigurationError
from .invalid_option_error import InvalidOptionError
from .mixed_channel_filter_error import MixedChannelFilterError
from .not_processable_handler_error import NotProcessableHandlerError
from .unknown_channel_error import UnknownChannelError
from .unknown_handler_error import UnknownHandlerError
from .unknown_service_error import UnknownServiceError

__all__ = [
    "CaptureConflictError",
    "CircularHandlerReferenceError",
    "EmptyStackError",
    "InvalidConfigurationError",
    "InvalidLevelError",
    "InvalidOptionError",
    "LoggingError",
    "MixedChannelFilterError",
    "NotProcessableHandlerError",
    "UnknownChannelError",
    "UnknownHandlerError",
    "UnknownServiceError",
]
