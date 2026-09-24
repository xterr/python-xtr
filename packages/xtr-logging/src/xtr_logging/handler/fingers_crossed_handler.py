"""Keep the whole request's log, but only once something went wrong."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_logging.exception.empty_stack_error import EmptyStackError
from xtr_logging.level import Level
from xtr_logging.resettable_interface import ResettableInterface

from .fingers_crossed.activation_strategy_interface import ActivationStrategyInterface
from .fingers_crossed.error_level_activation_strategy import ErrorLevelActivationStrategy
from .handler_interface import HandlerInterface
from .processable_handler_interface import ProcessableHandlerInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import TypeAlias

    from xtr_logging.level import LevelLike
    from xtr_logging.log_record import LogRecord
    from xtr_logging.processor.processor_interface import ProcessorInterface

    _HandlerFactory: TypeAlias = Callable[
        ["LogRecord | None", "FingersCrossedHandler"],
        HandlerInterface,
    ]

__all__ = ["FingersCrossedHandler"]


@final
class FingersCrossedHandler(HandlerInterface, ProcessableHandlerInterface, ResettableInterface):
    """Buffers every record, and forwards the lot the moment one is bad enough.

    A healthy request leaves nothing in the log; a failed one leaves its whole
    story, context and all, not just the line that failed. The activation
    strategy decides what "bad enough" means. After it fires, records pass
    straight through — unless ``stop_buffering`` is off, which starts a fresh
    buffer for whatever follows.

    ``passthru_level`` is the floor kept even when nothing triggered: on
    :meth:`close` or :meth:`reset`, records at that level or above are still
    forwarded, so a warning is not lost just because no error joined it.

    The wrapped handler may be given as a factory
    ``handler(record, self) -> HandlerInterface``, resolved and cached the
    first time it is needed — so an expensive handler is never built for a
    request that stays quiet.
    """

    def __init__(  # noqa: PLR0913, PLR0917 — every option is independent; all have defaults
        self,
        handler: HandlerInterface | _HandlerFactory,
        activation_strategy: ActivationStrategyInterface | LevelLike | None = None,
        buffer_size: int = 0,
        bubble: bool = True,
        stop_buffering: bool = True,
        passthru_level: LevelLike | None = None,
    ) -> None:
        """Wrap ``handler`` behind a buffer released by ``activation_strategy``.

        Args:
            handler: The handler flushed to, or a factory that builds it lazily.
            activation_strategy: What releases the buffer — a strategy, or a
                level for :class:`ErrorLevelActivationStrategy`. Defaults to
                activating on ``WARNING`` and above.
            buffer_size: The most records to keep before the oldest are
                dropped; ``0`` keeps everything until activation.
            bubble: Whether records still reach later handlers.
            stop_buffering: Whether to pass records straight through once
                activated, rather than buffering a fresh batch.
            passthru_level: A floor always flushed on close or reset, even with
                no activation; ``None`` flushes nothing in that case.

        Raises:
            InvalidLevelError: If a level argument names no level.
        """
        if activation_strategy is None:
            activation_strategy = ErrorLevelActivationStrategy(Level.WARNING)
        elif not isinstance(activation_strategy, ActivationStrategyInterface):
            activation_strategy = ErrorLevelActivationStrategy(activation_strategy)
        self._handler: HandlerInterface | _HandlerFactory = handler
        self._activation_strategy: ActivationStrategyInterface = activation_strategy
        self._buffer_size: int = buffer_size
        self._bubble: bool = bubble
        self._stop_buffering: bool = stop_buffering
        self._passthru_level: Level | None = (
            Level.parse(passthru_level) if passthru_level is not None else None
        )
        self._buffer: list[LogRecord] = []
        self._buffering: bool = True
        self._processors: tuple[ProcessorInterface, ...] = ()

    @property
    def processors(self) -> tuple[ProcessorInterface, ...]:
        """This handler's own processors, in the order they run."""
        return self._processors

    @override
    def push_processor(self, processor: ProcessorInterface, /) -> None:
        """Add ``processor`` in front of those already attached."""
        self._processors = (processor, *self._processors)

    @override
    def pop_processor(self) -> ProcessorInterface:
        """Remove and return the processor that runs first.

        Raises:
            EmptyStackError: If there is none.
        """
        if not self._processors:
            raise EmptyStackError(type(self).__name__, "processor")
        first, *rest = self._processors
        self._processors = tuple(rest)
        return first

    @override
    def is_handling(self, record: LogRecord, /) -> bool:
        """Always ``True``: everything is buffered until the buffer is released."""
        return True

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Buffer ``record``, or pass it through once the buffer has been released."""
        for processor in self._processors:
            record = processor(record)
        if self._buffering:
            self._buffer.append(record)
            if self._buffer_size > 0 and len(self._buffer) > self._buffer_size:
                _ = self._buffer.pop(0)
            if self._activation_strategy.is_handler_activated(record):
                self.activate()
        else:
            _ = self._resolve_handler(record).handle(record)
        return not self._bubble

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        """Offer each record in turn, as a logger would one by one."""
        for record in records:
            _ = self.handle(record)

    def activate(self) -> None:
        """Release the buffer now, whatever the strategy would have said."""
        if self._stop_buffering:
            self._buffering = False
        last = self._buffer[-1] if self._buffer else None
        self._resolve_handler(last).handle_batch(tuple(self._buffer))
        self._buffer = []

    @override
    def close(self) -> None:
        """Flush the passthru floor, then close the wrapped handler."""
        self._flush_buffer()
        self._resolve_handler().close()

    @override
    def reset(self) -> None:
        """Flush the passthru floor, reset processors, and reset the wrapped handler."""
        self._flush_buffer()
        for processor in self._processors:
            if isinstance(processor, ResettableInterface):
                processor.reset()
        handler = self._resolve_handler()
        if isinstance(handler, ResettableInterface):
            handler.reset()

    def clear(self) -> None:
        """Drop the buffer without forwarding it, and start buffering afresh."""
        self._buffer = []
        self.reset()

    def _flush_buffer(self) -> None:
        if self._passthru_level is not None:
            kept = [
                record for record in self._buffer if self._passthru_level.includes(record.level)
            ]
            if kept:
                self._resolve_handler(kept[-1]).handle_batch(tuple(kept))
        self._buffer = []
        self._buffering = True

    def _resolve_handler(self, record: LogRecord | None = None) -> HandlerInterface:
        handler = self._handler
        if isinstance(handler, HandlerInterface):
            return handler
        resolved = handler(record, self)
        self._handler = resolved
        return resolved
