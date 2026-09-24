"""Turning handler specs into handlers, each built once however often it is named."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final, final

from xtr_logging.bridge.stdlib.stdlib_handler import StdlibHandler
from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.exception.unknown_service_error import UnknownServiceError
from xtr_logging.handler.buffer_handler import BufferHandler
from xtr_logging.handler.console_handler import ConsoleHandler
from xtr_logging.handler.deduplication_handler import DeduplicationHandler
from xtr_logging.handler.fallback_group_handler import FallbackGroupHandler
from xtr_logging.handler.filter_handler import FilterHandler
from xtr_logging.handler.fingers_crossed.channel_level_activation_strategy import (
    ChannelLevelActivationStrategy,
)
from xtr_logging.handler.fingers_crossed.error_level_activation_strategy import (
    ErrorLevelActivationStrategy,
)
from xtr_logging.handler.fingers_crossed_handler import FingersCrossedHandler
from xtr_logging.handler.formattable_handler_interface import FormattableHandlerInterface
from xtr_logging.handler.group_handler import GroupHandler
from xtr_logging.handler.null_handler import NullHandler
from xtr_logging.handler.queue_handler import QueueHandler
from xtr_logging.handler.rotating_file_handler import RotatingFileHandler
from xtr_logging.handler.sampling_handler import SamplingHandler
from xtr_logging.handler.stream_handler import StreamHandler
from xtr_logging.handler.syslog_handler import SyslogHandler
from xtr_logging.handler.what_failure_group_handler import WhatFailureGroupHandler
from xtr_logging.verbosity import Verbosity

from .formatter_builder import build_formatter
from .handler_specs import (
    ConsoleHandlerSpec,
    FormattedHandlerSpec,
    NullHandlerSpec,
    RotatingFileHandlerSpec,
    ServiceHandlerSpec,
    StdlibHandlerSpec,
    StreamHandlerSpec,
    SyslogHandlerSpec,
)
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

if TYPE_CHECKING:
    from typing import TextIO

    from xtr_logging.handler.fingers_crossed.activation_strategy_interface import (
        ActivationStrategyInterface,
    )
    from xtr_logging.handler.handler_interface import HandlerInterface
    from xtr_logging.level import Level, LevelLike

    from .logging_config import HandlerSpec, LoggingConfig
    from .services import Services

__all__ = ["HandlerBuilder"]

_STANDARD_STREAMS: Final = ("stderr", "stdout")


@final
class HandlerBuilder:
    """Builds the handlers a configuration describes, sharing each by name.

    A handler named by two wrappers, or serving several channels, is one
    object — which is what makes a fingers-crossed buffer see every channel
    it serves, and a file handler hold one file open.
    """

    __slots__ = ("_built", "_config", "_services")

    def __init__(self, config: LoggingConfig, services: Services) -> None:
        """Build from ``config``, looking services up in ``services``."""
        self._config = config
        self._services = services
        self._built: dict[str, HandlerInterface] = {}

    @property
    def built(self) -> dict[str, HandlerInterface]:
        """Every handler built so far, by name."""
        return dict(self._built)

    def build(self, name: str) -> HandlerInterface:
        """Return the handler called ``name``, building it and what it wraps on first use.

        Raises:
            UnknownServiceError: If it names a service that was not supplied.
            InvalidOptionError: If an option cannot be used.
        """
        found = self._built.get(name)
        if found is None:
            spec = self._config.handlers[name]
            found = self._create(spec)
            formatter = (
                spec.formatter
                if isinstance(spec, FormattedHandlerSpec | ConsoleHandlerSpec)
                else None
            )
            if formatter is not None and isinstance(found, FormattableHandlerInterface):
                found.formatter = build_formatter(formatter, self._services)
            self._built[name] = found
        return found

    def _create(self, spec: HandlerSpec) -> HandlerInterface:  # noqa: C901, PLR0911, PLR0912 — one case per handler type
        match spec:
            case StreamHandlerSpec():
                return StreamHandler(
                    _stream(spec.path) if spec.path in _STANDARD_STREAMS else spec.path,
                    spec.level,
                    spec.bubble,
                    file_permission=spec.file_permission,
                )
            case RotatingFileHandlerSpec():
                return RotatingFileHandler(
                    spec.path,
                    spec.max_files,
                    spec.level,
                    spec.bubble,
                    date_format=spec.date_format,
                    filename_format=spec.filename_format,
                    file_permission=spec.file_permission,
                )
            case SyslogHandlerSpec():
                return SyslogHandler(
                    spec.ident,
                    spec.facility,
                    spec.level,
                    spec.bubble,
                    address=_address(spec.address),
                )
            case ConsoleHandlerSpec():
                return ConsoleHandler(
                    sys.stdout if spec.stream == "stdout" else None,
                    verbosity_levels=_verbosity_levels(spec.verbosity_levels),
                    bubble=spec.bubble,
                )
            case NullHandlerSpec():
                return NullHandler(spec.level)
            case StdlibHandlerSpec():
                return StdlibHandler(spec.logger, spec.level, spec.bubble)
            case ServiceHandlerSpec():
                service = self._services.handlers.get(spec.id)
                if service is None:
                    raise UnknownServiceError("handler", spec.id, tuple(self._services.handlers))
                return service
            case FingersCrossedHandlerSpec():
                return FingersCrossedHandler(
                    self.build(spec.handler),
                    self._activation_strategy(spec),
                    spec.buffer_size,
                    spec.bubble,
                    spec.stop_buffering,
                    spec.passthru_level,
                )
            case BufferHandlerSpec():
                return BufferHandler(
                    self.build(spec.handler),
                    spec.buffer_size,
                    spec.level,
                    spec.bubble,
                    spec.flush_on_overflow,
                )
            case FilterHandlerSpec():
                return FilterHandler(
                    self.build(spec.handler),
                    spec.accepted_levels if spec.accepted_levels is not None else spec.min_level,
                    spec.max_level,
                    spec.bubble,
                )
            case DeduplicationHandlerSpec():
                return DeduplicationHandler(
                    self.build(spec.handler),
                    spec.store,
                    spec.deduplication_level,
                    spec.time,
                    spec.bubble,
                )
            case SamplingHandlerSpec():
                return SamplingHandler(self.build(spec.handler), spec.factor)
            case QueueHandlerSpec():
                return QueueHandler(self.build(spec.handler), max_size=spec.max_size)
            case GroupHandlerSpec():
                return GroupHandler([self.build(m) for m in spec.members], spec.bubble)
            case WhatFailureGroupHandlerSpec():
                return WhatFailureGroupHandler([self.build(m) for m in spec.members], spec.bubble)
            case FallbackGroupHandlerSpec():
                return FallbackGroupHandler([self.build(m) for m in spec.members], spec.bubble)

    def _activation_strategy(self, spec: FingersCrossedHandlerSpec) -> ActivationStrategyInterface:
        if spec.activation_strategy is not None:
            strategies = self._services.activation_strategies
            found = strategies.get(spec.activation_strategy)
            if found is None:
                raise UnknownServiceError(
                    "activation strategy",
                    spec.activation_strategy,
                    tuple(strategies),
                )
            return found
        if spec.channel_levels:
            return ChannelLevelActivationStrategy(spec.action_level, spec.channel_levels)
        return ErrorLevelActivationStrategy(spec.action_level)


def _stream(name: str) -> TextIO:
    return sys.stdout if name == "stdout" else sys.stderr


def _address(address: str) -> str | tuple[str, int]:
    if address.startswith("/"):
        return address
    host, _, port = address.rpartition(":")
    if not host or not port.isdigit():
        raise InvalidOptionError("address", address, "expected host:port or a socket path")
    return host, int(port)


def _verbosity_levels(
    levels: dict[str, Level | str] | None,
) -> dict[Verbosity, LevelLike] | None:
    if levels is None:
        return None
    mapped: dict[Verbosity, LevelLike] = {}
    for name, level in levels.items():
        verbosity = Verbosity.__members__.get(name.upper())
        if verbosity is None:
            raise InvalidOptionError("verbosity_levels", name, f"expected one of {_VERBOSITIES}")
        mapped[verbosity] = level
    return mapped


_VERBOSITIES: Final = ", ".join(name.lower() for name in Verbosity.__members__)
