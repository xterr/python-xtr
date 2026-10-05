"""Turning handler configurations into handlers, each built once however often it is named."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final, assert_never, final

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
from .handler_configs import (
    ConsoleHandlerConfig,
    FormattedHandlerConfig,
    NullHandlerConfig,
    RotatingFileHandlerConfig,
    ServiceHandlerConfig,
    StdlibHandlerConfig,
    StreamHandlerConfig,
    SyslogHandlerConfig,
)
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

if TYPE_CHECKING:
    from typing import TextIO

    from xtr_logging_contracts import Level, LevelLike

    from xtr_logging.handler.fingers_crossed.activation_strategy_interface import (
        ActivationStrategyInterface,
    )
    from xtr_logging.handler.handler_interface import HandlerInterface

    from .logging_config import HandlerConfig, LoggingConfig
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
            handler_config = self._config.handlers[name]
            found = self._create(name, handler_config)
            formatter = (
                handler_config.formatter
                if isinstance(handler_config, FormattedHandlerConfig | ConsoleHandlerConfig)
                else None
            )
            if formatter is not None and isinstance(found, FormattableHandlerInterface):
                found.formatter = build_formatter(formatter, self._services)
            self._built[name] = found
        return found

    def _create(self, name: str, config: HandlerConfig) -> HandlerInterface:  # noqa: C901, PLR0911, PLR0912 — one case per handler type
        match config:
            case StreamHandlerConfig():
                return StreamHandler(
                    _stream(config.path) if config.path in _STANDARD_STREAMS else config.path,
                    config.level,
                    config.bubble,
                    file_permission=config.file_permission,
                )
            case RotatingFileHandlerConfig():
                return RotatingFileHandler(
                    config.path,
                    config.max_files,
                    config.level,
                    config.bubble,
                    date_format=config.date_format,
                    filename_format=config.filename_format,
                    file_permission=config.file_permission,
                )
            case SyslogHandlerConfig():
                return SyslogHandler(
                    config.ident,
                    config.facility,
                    config.level,
                    config.bubble,
                    address=_address(config.address),
                )
            case ConsoleHandlerConfig():
                return ConsoleHandler(
                    sys.stdout if config.stream == "stdout" else None,
                    verbosity_levels=_verbosity_levels(config.verbosity_levels),
                    bubble=config.bubble,
                )
            case NullHandlerConfig():
                return NullHandler(config.level)
            case StdlibHandlerConfig():
                return StdlibHandler(config.logger, config.level, config.bubble)
            case ServiceHandlerConfig():
                service = self._services.handlers.get(config.id)
                if service is None:
                    raise UnknownServiceError("handler", config.id, tuple(self._services.handlers))
                return service
            case FingersCrossedHandlerConfig():
                return FingersCrossedHandler(
                    self.build(config.handler),
                    self._activation_strategy(config),
                    config.buffer_size,
                    config.bubble,
                    config.stop_buffering,
                    config.passthru_level,
                )
            case BufferHandlerConfig():
                return BufferHandler(
                    self.build(config.handler),
                    config.buffer_size,
                    config.level,
                    config.bubble,
                    config.flush_on_overflow,
                )
            case FilterHandlerConfig():
                return FilterHandler(
                    self.build(config.handler),
                    config.accepted_levels
                    if config.accepted_levels is not None
                    else config.min_level,
                    config.max_level,
                    config.bubble,
                )
            case DeduplicationHandlerConfig():
                return DeduplicationHandler(
                    self.build(config.handler),
                    config.store,
                    config.deduplication_level,
                    config.time,
                    config.bubble,
                    buffer_limit=config.buffer_limit,
                    flush_on_overflow=config.flush_on_overflow,
                    name=name,
                )
            case SamplingHandlerConfig():
                return SamplingHandler(self.build(config.handler), config.factor, config.bubble)
            case QueueHandlerConfig():
                return QueueHandler(self.build(config.handler), max_size=config.max_size)
            case GroupHandlerConfig():
                return GroupHandler([self.build(m) for m in config.members], config.bubble)
            case WhatFailureGroupHandlerConfig():
                return WhatFailureGroupHandler(
                    [self.build(m) for m in config.members], config.bubble
                )
            case FallbackGroupHandlerConfig():
                return FallbackGroupHandler([self.build(m) for m in config.members], config.bubble)
            case _:
                # A configuration added to the union without a case fails here, not on a record.
                assert_never(config)

    def _activation_strategy(
        self,
        config: FingersCrossedHandlerConfig,
    ) -> ActivationStrategyInterface:
        if config.activation_strategy is not None:
            strategies = self._services.activation_strategies
            found = strategies.get(config.activation_strategy)
            if found is None:
                raise UnknownServiceError(
                    "activation strategy",
                    config.activation_strategy,
                    tuple(strategies),
                )
            return found
        if config.channel_levels:
            return ChannelLevelActivationStrategy(config.action_level, config.channel_levels)
        return ErrorLevelActivationStrategy(config.action_level)


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
        verbosity = _MAPPABLE.get(name.upper())
        if verbosity is None:
            raise InvalidOptionError("verbosity_levels", name, f"expected one of {_VERBOSITIES}")
        mapped[verbosity] = level
    return mapped


# Silent prints nothing, whatever it maps to, so it takes no level.
_MAPPABLE: Final = {
    name: verbosity
    for name, verbosity in Verbosity.__members__.items()
    if verbosity is not Verbosity.SILENT
}
_VERBOSITIES: Final = ", ".join(name.lower() for name in _MAPPABLE)
