"""Describing logging as settings.

Pure data: which channels exist, which handlers there are and which channels
each serves, and which processors run where. It builds nothing — hand it to
:class:`~xtr_logging.logger_factory.LoggerFactory` for that::

    CONFIG = LoggingConfig(
        channels=("security", "billing"),
        handlers={
            "main": FingersCrossedHandlerSpec(action_level="error", handler="file"),
            "file": StreamHandlerSpec(path="var/log/prod.log"),
            "console": ConsoleHandlerSpec(channels=("!event",)),
        },
        processors=(PlaceholderProcessorSpec(),),
    )

or, from a parsed file, :meth:`LoggingConfig.from_mapping`. Keeping it inert
is what lets it come from a settings module, TOML or an environment without
opening a single file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

import msgspec

from xtr_logging.exception.capture_conflict_error import CaptureConflictError
from xtr_logging.exception.circular_handler_reference_error import CircularHandlerReferenceError
from xtr_logging.exception.invalid_configuration_error import InvalidConfigurationError
from xtr_logging.exception.unknown_channel_error import UnknownChannelError
from xtr_logging.exception.unknown_handler_error import UnknownHandlerError

from .capture_spec import CaptureSpec  # noqa: TC001 — msgspec reads field types at runtime
from .handler_specs import (
    ConsoleHandlerSpec,
    NullHandlerSpec,
    RotatingFileHandlerSpec,
    ServiceHandlerSpec,
    StdlibHandlerSpec,
    StreamHandlerSpec,
    SyslogHandlerSpec,
)
from .processor_specs import ProcessorSpec  # noqa: TC001 — msgspec reads field types at runtime
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
    from collections.abc import Mapping

__all__ = ["HandlerSpec", "LoggingConfig"]

HandlerSpec: TypeAlias = (
    StreamHandlerSpec
    | RotatingFileHandlerSpec
    | SyslogHandlerSpec
    | ConsoleHandlerSpec
    | NullHandlerSpec
    | StdlibHandlerSpec
    | ServiceHandlerSpec
    | FingersCrossedHandlerSpec
    | BufferHandlerSpec
    | FilterHandlerSpec
    | DeduplicationHandlerSpec
    | SamplingHandlerSpec
    | QueueHandlerSpec
    | GroupHandlerSpec
    | WhatFailureGroupHandlerSpec
    | FallbackGroupHandlerSpec
)
"""Any handler entry, told apart by its ``type``."""


def _no_handlers() -> dict[str, HandlerSpec]:
    return {}


class LoggingConfig(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """The channels, handlers and processors of an application.

    Checked as it is made: every handler a wrapper names must exist, wrappers
    must not nest each other in a loop, and a processor may only target a
    channel or handler that exists.

    Attributes:
        handlers: Named handlers, in declaration order. Wrappers name the
            handlers they wrap; those leave every channel's stack.
        channels: Channels beyond :attr:`default_channel`. Channels named in
            a handler's ``channels`` list are declared too.
        processors: Processors and where they run.
        default_channel: The channel a logger is on when none is asked for.
        capture: Send the standard library's logging into channels, and only
            there. Off when omitted.
    """

    handlers: dict[str, HandlerSpec] = msgspec.field(default_factory=_no_handlers)
    channels: tuple[str, ...] = ()
    processors: tuple[ProcessorSpec, ...] = ()
    default_channel: str = "app"
    capture: CaptureSpec | None = None

    def __post_init__(self) -> None:
        """Check every cross-reference.

        Raises:
            UnknownHandlerError: If a wrapper or processor names a missing handler.
            CircularHandlerReferenceError: If wrappers nest each other in a loop.
            UnknownChannelError: If a processor or the capture names a missing
                channel.
            CaptureConflictError: If capture is on while a ``stdlib`` handler
                sends records back into the standard library.
        """
        known = tuple(self.handlers)
        for name, spec in self.handlers.items():
            for reference in spec.references:
                if reference not in self.handlers:
                    raise UnknownHandlerError(reference, f"handler {name!r}", known)
        for name in self.handlers:
            self._check_acyclic(name, ())
        for processor in self.processors:
            if processor.handler is not None and processor.handler not in self.handlers:
                raise UnknownHandlerError(processor.handler, "a processor", known)
            if processor.channel is not None and processor.channel not in self.all_channels:
                raise UnknownChannelError(processor.channel, self.all_channels)
        if self.capture is not None:
            self._check_capture(self.capture)

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> LoggingConfig:
        """Read configuration from plain data — parsed TOML, JSON or YAML.

        Values are not coerced: ``"3"`` is not a number. Levels are written
        by name (``"error"``) or value (``400``).

        Raises:
            InvalidConfigurationError: If the data does not fit, naming where.
            UnknownHandlerError: If a wrapper or processor names a missing handler.
            CircularHandlerReferenceError: If wrappers nest each other in a loop.
            UnknownChannelError: If a processor targets a missing channel.
        """
        try:
            return msgspec.convert(data, cls)
        except msgspec.ValidationError as error:
            raise InvalidConfigurationError(str(error)) from error

    @property
    def all_channels(self) -> tuple[str, ...]:
        """Every declared channel: the default, the listed, then those named by handlers."""
        found = dict.fromkeys((self.default_channel, *self.channels))
        for spec in self.handlers.values():
            channel_filter = spec.channel_filter
            if channel_filter is not None:
                found.update(dict.fromkeys(sorted(channel_filter.channels)))
        return tuple(found)

    @property
    def nested_handlers(self) -> frozenset[str]:
        """Handlers kept off every channel's stack: those named by another, or marked nested."""
        referenced = {reference for spec in self.handlers.values() for reference in spec.references}
        marked = {name for name, spec in self.handlers.items() if spec.nested}
        return frozenset(referenced | marked)

    @property
    def top_level_handlers(self) -> tuple[str, ...]:
        """Handlers on the channel stacks, highest priority first, ties in declaration order."""
        nested = self.nested_handlers
        candidates = [name for name in self.handlers if name not in nested]
        return tuple(sorted(candidates, key=lambda name: -self.handlers[name].priority))

    def _check_capture(self, capture: CaptureSpec) -> None:
        for channel in capture.channels:
            if channel not in self.all_channels:
                raise UnknownChannelError(channel, self.all_channels)
        for name, spec in self.handlers.items():
            if isinstance(spec, StdlibHandlerSpec):
                raise CaptureConflictError(name)

    def _check_acyclic(self, name: str, path: tuple[str, ...]) -> None:
        if name in path:
            raise CircularHandlerReferenceError((*path[path.index(name) :], name))
        for reference in self.handlers[name].references:
            self._check_acyclic(reference, (*path, name))
