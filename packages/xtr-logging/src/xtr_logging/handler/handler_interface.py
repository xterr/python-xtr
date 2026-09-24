"""Where records go: a file, a socket, another handler."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.log_record import LogRecord

__all__ = ["HandlerInterface"]


@runtime_checkable
class HandlerInterface(Protocol):
    """Receives records from a logger and does something with them.

    A logger holds a stack of handlers and offers each record to them in
    turn. A handler that returns ``True`` from :meth:`handle` stops the record
    there — that is what ``bubble=False`` means — so a later handler never
    sees it.
    """

    def is_handling(self, record: LogRecord, /) -> bool:
        """Whether :meth:`handle` would do anything with ``record``.

        Asked before processors run, so it must be cheap and must not depend
        on anything a processor adds. Usually just a level check.
        """
        ...

    def handle(self, record: LogRecord, /) -> bool:
        """Handle ``record``; return ``True`` to stop it reaching later handlers."""
        ...

    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        """Handle several records at once, as a buffer flushes them."""
        ...

    def close(self) -> None:
        """Flush and release what the handler holds. It may be used again after."""
        ...
