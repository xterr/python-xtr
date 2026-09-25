"""Building a logger per channel from a configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, Self, final

from xtr_logging_contracts import ResettableInterface

from .bridge.stdlib.stdlib_capture import StdlibCapture
from .config.handler_builder import HandlerBuilder
from .config.processor_builder import build_processor
from .config.services import Services
from .exception.not_processable_handler_error import NotProcessableHandlerError
from .exception.unknown_channel_error import UnknownChannelError
from .exception.unknown_handler_error import UnknownHandlerError
from .handler.console_handler import ConsoleHandler
from .handler.processable_handler_interface import ProcessableHandlerInterface
from .logger import Logger
from .processor.processor_registry import default_processor_registry

if TYPE_CHECKING:
    from types import TracebackType
    from typing import IO

    from xtr_clock import ClockInterface

    from .config.logging_config import LoggingConfig
    from .handler.handler_interface import HandlerInterface
    from .processor.processor_interface import ProcessorInterface
    from .processor.processor_registry import ProcessorRegistry
    from .verbosity import Verbosity

__all__ = ["LoggerFactory"]


class _Placed(NamedTuple):
    processor: ProcessorInterface
    channel: str | None
    handler: str | None
    priority: int


@final
class LoggerFactory:
    """Builds one logger per channel, sharing handlers between them.

    Every handler in the configuration is built once, as the factory is
    made, so a missing service fails here rather than on the first record.
    Files and sockets still open lazily, on first write. A channel's logger
    gets every top-level handler whose ``channels`` accept it, highest
    priority first, and every processor not aimed elsewhere::

        factory = LoggerFactory(CONFIG)
        security = factory.logger("security")

    With a ``capture`` section, the standard library's logging is taken over
    as the factory is made, and given back when it is closed.

    Close the factory when the process ends — or use it as a context
    manager — so buffered and queued records are written.
    """

    __slots__ = ("_builder", "_capture", "_clock", "_config", "_loggers", "_placed")

    def __init__(
        self,
        config: LoggingConfig,
        *,
        services: Services | None = None,
        registry: ProcessorRegistry | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Build every handler and processor ``config`` describes.

        Args:
            config: The channels, handlers and processors.
            services: Objects the configuration names by id.
            registry: Where :func:`~xtr_logging.decorator.as_processor`
                declarations are read from; the process-wide registry by default.
            clock: Where every logger reads the time.

        Raises:
            UnknownServiceError: If the configuration names a missing service.
            UnknownChannelError: If a declared processor targets a missing channel.
            UnknownHandlerError: If a declared processor targets a missing handler.
            NotProcessableHandlerError: If a processor targets a handler that
                runs none.
        """
        resolved = services if services is not None else Services()
        declared = registry if registry is not None else default_processor_registry()
        self._config = config
        self._clock = clock
        self._builder = HandlerBuilder(config, resolved)
        self._loggers: dict[str, Logger] = {}
        for name in config.handlers:
            _ = self._builder.build(name)
        placed = [
            _Placed(build_processor(spec, resolved), spec.channel, spec.handler, spec.priority)
            for spec in config.processors
        ]
        placed.extend(
            _Placed(d.processor, d.channel, d.handler, d.priority) for d in declared.descriptors
        )
        self._placed = sorted(placed, key=lambda entry: -entry.priority)
        self._attach_handler_processors()
        self._capture: StdlibCapture | None = self._build_capture()
        if self._capture is not None:
            self._capture.install()

    @property
    def channels(self) -> tuple[str, ...]:
        """Every channel a logger can be asked for."""
        return self._config.all_channels

    def logger(self, channel: str | None = None) -> Logger:
        """Return the logger for ``channel``, or for the default channel.

        The same logger is returned every time for the same channel.

        Raises:
            UnknownChannelError: If ``channel`` is not declared.
        """
        name = channel if channel is not None else self._config.default_channel
        found = self._loggers.get(name)
        if found is None:
            if name not in self._config.all_channels:
                raise UnknownChannelError(name, self._config.all_channels)
            found = Logger(
                name,
                [self._builder.build(handler) for handler in self._handlers_for(name)],
                [
                    entry.processor
                    for entry in self._placed
                    if entry.handler is None and entry.channel in {None, name}
                ],
                clock=self._clock,
            )
            self._loggers[name] = found
        return found

    def handler(self, name: str) -> HandlerInterface:
        """Return the handler configured as ``name`` — a test handler, say.

        Raises:
            UnknownHandlerError: If no handler has that name.
        """
        if name not in self._config.handlers:
            raise UnknownHandlerError(name, "LoggerFactory.handler()", tuple(self._config.handlers))
        return self._builder.build(name)

    def set_verbosity(self, verbosity: Verbosity) -> None:
        """Set the verbosity of every console handler — what ``-v`` flags decide."""
        for built in self._builder.built.values():
            if isinstance(built, ConsoleHandler):
                built.set_verbosity(verbosity)

    def set_console_stream(self, stream: IO[str] | None, *, colors: bool | None = None) -> None:
        """Point every console handler at ``stream`` — a command's error output, typically.

        ``None`` is standard error, resolved at write time. ``colors`` forces
        colours on or off; ``None`` colours only a real terminal.
        """
        for built in self._builder.built.values():
            if isinstance(built, ConsoleHandler):
                built.set_stream(stream, colors=colors)

    def reset(self) -> None:
        """End a unit of work: reset every handler and processor that holds state."""
        for built in self._owned_handlers():
            if isinstance(built, ResettableInterface):
                built.reset()
        for entry in self._placed:
            if entry.handler is None and isinstance(entry.processor, ResettableInterface):
                entry.processor.reset()

    @property
    def capture(self) -> StdlibCapture | None:
        """The standard-library capture, if the configuration asks for one."""
        return self._capture

    def close(self) -> None:
        """Give the standard library its logging back, then close every handler.

        Whatever is buffered or queued is written.
        """
        if self._capture is not None:
            self._capture.release()
        for built in self._owned_handlers():
            built.close()

    def __enter__(self) -> Self:
        """Use the factory for the ``with`` block, closing it after."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close every handler."""
        self.close()

    def _build_capture(self) -> StdlibCapture | None:
        spec = self._config.capture
        if spec is None:
            return None
        loggers = {name: spec.logger_spec(name) for name in spec.loggers}
        return StdlibCapture(
            self.logger(spec.channel),
            level=spec.level,
            levels={name: entry.level for name, entry in loggers.items()},
            routes={
                name: self.logger(entry.channel)
                for name, entry in loggers.items()
                if entry.channel is not None
            },
        )

    def _handlers_for(self, channel: str) -> list[str]:
        accepted: list[str] = []
        for name in self._config.top_level_handlers:
            channel_filter = self._config.handlers[name].channel_filter
            if channel_filter is None or channel_filter.accepts(channel):
                accepted.append(name)
        return accepted

    def _owned_handlers(self) -> list[HandlerInterface]:
        """Handlers no wrapper owns; a wrapper closes and resets what it wraps."""
        referenced = {
            reference for spec in self._config.handlers.values() for reference in spec.references
        }
        return [
            self._builder.build(name) for name in self._config.handlers if name not in referenced
        ]

    def _attach_handler_processors(self) -> None:
        known_channels = self._config.all_channels
        for entry in reversed(self._placed):
            if entry.channel is not None and entry.channel not in known_channels:
                raise UnknownChannelError(entry.channel, known_channels)
            if entry.handler is None:
                continue
            if entry.handler not in self._config.handlers:
                known = tuple(self._config.handlers)
                raise UnknownHandlerError(entry.handler, "a processor", known)
            target = self._builder.build(entry.handler)
            if not isinstance(target, ProcessableHandlerInterface):
                raise NotProcessableHandlerError(entry.handler)
            target.push_processor(entry.processor)
