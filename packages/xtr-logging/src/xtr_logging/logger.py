"""A channel: a name, a stack of handlers, and the processors in front of them."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import Clock
from xtr_logging_contracts import AbstractLogger, Level
from xtr_service_contracts import ResettableInterface

from .exception.empty_stack_error import EmptyStackError
from .log_record import LogRecord

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable, Sequence

    from xtr_clock import ClockInterface
    from xtr_logging_contracts import Context, LevelLike

    from .handler.handler_interface import HandlerInterface
    from .processor.processor_interface import ProcessorInterface

__all__ = ["Logger"]

_LOOP_WARNING: Final = (
    "A possible infinite logging loop was detected and aborted. It appears some of your "
    "handler code is triggering logging, see the previous log record for a hint as to "
    "what may be the cause."
)
_WARN_AT_DEPTH: Final = 3
_DROP_AT_DEPTH: Final = 5

# How deeply records are being logged from inside the handling of another record.
# Shared by every logger: a handler logging through a second logger is as much a
# loop as one logging through its own.
_depth: ContextVar[int] = ContextVar("xtr_logging_depth", default=0)


@final
class Logger(AbstractLogger, ResettableInterface):
    """A named channel that turns calls into records and offers them to handlers.

    Handlers are consulted in stack order — the one pushed last first — and a
    record stops at the first handler that does not let it bubble. Processors
    run once per record, in order, and only once some handler has said it
    will handle it.

    A logger is mutable: handlers and processors are pushed
    and popped while an application is being wired. The stacks are swapped
    as whole tuples, so a record being logged on another thread always sees
    a complete stack.
    """

    def __init__(  # noqa: PLR0913 — everything past `processors` is keyword-only
        self,
        name: str,
        handlers: Sequence[HandlerInterface] = (),
        processors: Sequence[ProcessorInterface] = (),
        *,
        clock: ClockInterface | None = None,
        exception_handler: Callable[[Exception, LogRecord], None] | None = None,
        detect_cycles: bool = True,
    ) -> None:
        """Build a channel called ``name``.

        Args:
            name: The channel every record from this logger carries.
            handlers: Consulted first to last.
            processors: Run first to last on every record that is handled.
            clock: Where record times come from. By default, whichever clock is in
                force as each record is made — the system's, unless a test installed
                another with :meth:`xtr_clock.Clock.using`.
            exception_handler: Called with any exception a handler or processor
                raises, instead of letting it propagate to the caller.
            detect_cycles: Abort records logged from inside the handling of
                another record, three levels deep, rather than recursing until
                the stack overflows.
        """
        self._name = name
        self._handlers: tuple[HandlerInterface, ...] = tuple(handlers)
        self._processors: tuple[ProcessorInterface, ...] = tuple(processors)
        self._clock: ClockInterface = clock if clock is not None else Clock()
        self._exception_handler = exception_handler
        self._detect_cycles = detect_cycles

    @property
    def name(self) -> str:
        """The channel this logger writes to."""
        return self._name

    @property
    def handlers(self) -> tuple[HandlerInterface, ...]:
        """The handler stack, in the order records are offered to it."""
        return self._handlers

    @property
    def processors(self) -> tuple[ProcessorInterface, ...]:
        """The processors, in the order they run."""
        return self._processors

    def with_name(self, name: str) -> Logger:
        """Return a logger for channel ``name`` sharing these handlers and processors.

        The stacks are copied, the objects in them are not: pushing a handler
        onto one logger leaves the other as it was, while a handler both hold
        is the same handler.
        """
        return Logger(
            name,
            self._handlers,
            self._processors,
            clock=self._clock,
            exception_handler=self._exception_handler,
            detect_cycles=self._detect_cycles,
        )

    def push_handler(self, handler: HandlerInterface) -> None:
        """Put ``handler`` on top of the stack, where it is consulted first."""
        self._handlers = (handler, *self._handlers)

    def pop_handler(self) -> HandlerInterface:
        """Remove and return the handler on top of the stack.

        Raises:
            EmptyStackError: If the stack is empty.
        """
        if not self._handlers:
            raise EmptyStackError(f"logger {self._name!r}", "handler")
        top, *rest = self._handlers
        self._handlers = tuple(rest)
        return top

    def set_handlers(self, handlers: Sequence[HandlerInterface]) -> None:
        """Replace the whole stack; ``handlers[0]`` is consulted first."""
        self._handlers = tuple(handlers)

    def push_processor(self, processor: ProcessorInterface) -> None:
        """Put ``processor`` in front of the others, where it runs first."""
        self._processors = (processor, *self._processors)

    def pop_processor(self) -> ProcessorInterface:
        """Remove and return the processor that runs first.

        Raises:
            EmptyStackError: If there are no processors.
        """
        if not self._processors:
            raise EmptyStackError(f"logger {self._name!r}", "processor")
        first, *rest = self._processors
        self._processors = tuple(rest)
        return first

    def is_handling(self, level: LevelLike) -> bool:
        """Whether any handler would handle a record at ``level`` from this channel."""
        probe = LogRecord(self._clock.now(), self._name, Level.parse(level), "")
        return any(handler.is_handling(probe) for handler in self._handlers)

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        """Log ``message`` at ``level``.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        _ = self.add_record(level, message, context)

    def add_record(
        self,
        level: LevelLike,
        message: str,
        context: Context | None = None,
        *,
        datetime: dt.datetime | None = None,
    ) -> bool:
        """Offer a record to the handlers; return whether any handled it.

        ``datetime`` overrides the clock, for records that happened earlier —
        one relayed from the standard library, say.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        record = LogRecord(
            datetime if datetime is not None else self._clock.now(),
            self._name,
            Level.parse(level),
            message,
            context if context is not None else {},
        )
        if not self._detect_cycles:
            return self._dispatch(record)
        depth = _depth.get() + 1
        token = _depth.set(depth)
        try:
            if depth == _WARN_AT_DEPTH:
                self.warning(_LOOP_WARNING)
                return False
            if depth >= _DROP_AT_DEPTH:
                return False
            return self._dispatch(record)
        finally:
            _depth.reset(token)

    def close(self) -> None:
        """Close every handler, flushing whatever they buffer."""
        for handler in self._handlers:
            handler.close()

    @override
    def reset(self) -> None:
        """End a unit of work: reset every handler and processor that holds state.

        Call it between the messages or requests of a long-running process, so
        a buffer or an activated fingers-crossed handler from one does not
        carry into the next.
        """
        for handler in self._handlers:
            if isinstance(handler, ResettableInterface):
                handler.reset()
        for processor in self._processors:
            if isinstance(processor, ResettableInterface):
                processor.reset()

    def _dispatch(self, record: LogRecord) -> bool:
        processed: LogRecord | None = None
        try:
            for handler in self._handlers:
                if processed is None:
                    if not handler.is_handling(record):
                        continue
                    processed = self._process(record)
                if handler.handle(processed):
                    break
        except Exception as error:
            if self._exception_handler is None:
                raise
            self._exception_handler(error, processed if processed is not None else record)
        return processed is not None

    def _process(self, record: LogRecord) -> LogRecord:
        for processor in self._processors:
            record = processor(record)
        return record
