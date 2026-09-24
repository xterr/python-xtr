"""A step that adds to a record before it is written."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_logging.log_record import LogRecord

__all__ = ["ProcessorInterface"]


@runtime_checkable
class ProcessorInterface(Protocol):
    """Takes a record and returns it, usually with something added to ``extra``.

    Any callable of that shape qualifies, so a plain function is a processor.
    Records are immutable: return a new one, via
    :meth:`~xtr_logging.log_record.LogRecord.with_extra` or
    :func:`dataclasses.replace`.

    A processor attached to a logger runs once per record, and only if some
    handler is going to handle it — so an expensive one costs nothing for a
    record every handler would have dropped.
    """

    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record``, enriched."""
        ...
