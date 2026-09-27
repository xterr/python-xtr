"""Hold records back and hand them over in one batch, instead of one at a time."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_logging_contracts import Level
from xtr_service_contracts import ResetInterface

from ._processor_stack import ProcessorStack
from .abstract_handler import AbstractHandler

if TYPE_CHECKING:
    from xtr_logging_contracts import LevelLike

    from xtr_logging.log_record import LogRecord

    from .handler_interface import HandlerInterface

__all__ = ["BufferHandler"]


class BufferHandler(AbstractHandler, ProcessorStack):
    """Keeps records in memory and forwards them together when flushed.

    A mail handler that sent one message per record would send a flood; wrap
    it in one of these and it sends a single message per request instead. The
    buffer is handed on as a batch on :meth:`close`, on :meth:`reset`, or when
    it overflows a limit that flushes rather than discards.

    It never registers an ``atexit`` hook of its own: the
    process that owns the buffer — the logger factory, usually — flushes it by
    calling :meth:`close`, so nothing is written after interpreter shutdown has
    begun.
    """

    def __init__(
        self,
        handler: HandlerInterface,
        buffer_limit: int = 0,
        level: LevelLike = Level.DEBUG,
        bubble: bool = True,
        flush_on_overflow: bool = False,
    ) -> None:
        """Buffer records for ``handler``.

        Args:
            handler: Where the buffer is flushed to, as a batch.
            buffer_limit: The most records to hold; ``0`` means no limit. Past
                it, the oldest record is dropped unless ``flush_on_overflow``.
            level: Buffer only records at this level or above.
            bubble: Whether a buffered record still reaches later handlers.
            flush_on_overflow: Flush the whole buffer when it fills, rather
                than dropping the oldest record to make room.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        super().__init__(level, bubble)
        self._handler: HandlerInterface = handler
        self._buffer_limit: int = buffer_limit
        self._flush_on_overflow: bool = flush_on_overflow
        self._buffer: list[LogRecord] = []

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Buffer ``record`` if it is at this handler's level.

        Returns ``True`` only when ``bubble`` is off, exactly as any handler
        that has taken a record does — the record is buffered, not yet written.
        """
        if record.level < self._level:
            return False
        if self._buffer_limit > 0 and len(self._buffer) == self._buffer_limit:
            if self._flush_on_overflow:
                self.flush()
            else:
                _ = self._buffer.pop(0)
        self._buffer.append(self._process(record))
        return not self._bubble

    def flush(self) -> None:
        """Hand the whole buffer to the wrapped handler, then empty it."""
        if not self._buffer:
            return
        self._handler.handle_batch(tuple(self._buffer))
        self.clear()

    def clear(self) -> None:
        """Empty the buffer without forwarding anything."""
        self._buffer = []

    @override
    def close(self) -> None:
        """Flush what is buffered, then close the wrapped handler."""
        self.flush()
        self._handler.close()

    @override
    def reset(self) -> None:
        """Flush the buffer and reset this handler's processors and the wrapped one."""
        self.flush()
        super().reset()
        self._reset_processors()
        if isinstance(self._handler, ResetInterface):
            self._handler.reset()
