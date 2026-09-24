"""Fan one record out to several handlers at once."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_logging.exception.empty_stack_error import EmptyStackError
from xtr_logging.resettable_interface import ResettableInterface

from .handler_interface import HandlerInterface
from .processable_handler_interface import ProcessableHandlerInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.log_record import LogRecord
    from xtr_logging.processor.processor_interface import ProcessorInterface

__all__ = ["GroupHandler"]


class GroupHandler(HandlerInterface, ProcessableHandlerInterface, ResettableInterface):
    """Forwards every record to each of a group of handlers.

    One place to attach a file, a console and a syslog to a channel, treated
    as a single handler on its stack. Records are immutable, so nothing is
    cloned before it is handed on — every member sees the same record.
    """

    def __init__(self, handlers: Sequence[HandlerInterface], bubble: bool = True) -> None:
        """Forward to each of ``handlers``, letting records bubble on if ``bubble``."""
        self._handlers: tuple[HandlerInterface, ...] = tuple(handlers)
        self._bubble: bool = bubble
        self._processors: tuple[ProcessorInterface, ...] = ()

    @property
    def handlers(self) -> tuple[HandlerInterface, ...]:
        """The handlers this group forwards to."""
        return self._handlers

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
        """Whether any member would handle ``record``."""
        return any(handler.is_handling(record) for handler in self._handlers)

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Offer ``record`` to every member, after this handler's own processors."""
        record = self._process(record)
        for handler in self._handlers:
            _ = handler.handle(record)
        return not self._bubble

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        """Offer the whole batch to every member."""
        processed = tuple(self._process(record) for record in records)
        for handler in self._handlers:
            handler.handle_batch(processed)

    @override
    def reset(self) -> None:
        """Reset this handler's processors and every member that holds state."""
        for processor in self._processors:
            if isinstance(processor, ResettableInterface):
                processor.reset()
        for handler in self._handlers:
            if isinstance(handler, ResettableInterface):
                handler.reset()

    @override
    def close(self) -> None:
        """Close every member."""
        for handler in self._handlers:
            handler.close()

    def _process(self, record: LogRecord) -> LogRecord:
        for processor in self._processors:
            record = processor(record)
        return record
