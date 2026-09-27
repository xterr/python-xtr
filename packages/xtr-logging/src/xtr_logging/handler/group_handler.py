"""Fan one record out to several handlers at once."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_service_contracts import ResetInterface

from ._processor_stack import ProcessorStack
from .handler_interface import HandlerInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.log_record import LogRecord

__all__ = ["GroupHandler"]


class GroupHandler(ProcessorStack, HandlerInterface, ResetInterface):
    """Forwards every record to each of a group of handlers.

    One place to attach a file, a console and a syslog to a channel, treated
    as a single handler on its stack. Records are immutable, so nothing is
    cloned before it is handed on — every member sees the same record.
    """

    def __init__(self, handlers: Sequence[HandlerInterface], bubble: bool = True) -> None:
        """Forward to each of ``handlers``, letting records bubble on if ``bubble``."""
        self._handlers: tuple[HandlerInterface, ...] = tuple(handlers)
        self._bubble: bool = bubble

    @property
    def handlers(self) -> tuple[HandlerInterface, ...]:
        """The handlers this group forwards to."""
        return self._handlers

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
        self._reset_processors()
        for handler in self._handlers:
            if isinstance(handler, ResetInterface):
                handler.reset()

    @override
    def close(self) -> None:
        """Close every member."""
        for handler in self._handlers:
            handler.close()
