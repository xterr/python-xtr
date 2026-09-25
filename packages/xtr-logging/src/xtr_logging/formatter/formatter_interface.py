"""Turning records into the text a handler writes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.log_record import LogRecord

__all__ = ["FormatterInterface"]


@runtime_checkable
class FormatterInterface(Protocol):
    """Renders records as text."""

    def format(self, record: LogRecord, /) -> str:
        """Render one record."""
        ...

    def format_batch(self, records: Sequence[LogRecord], /) -> str:
        """Render several records as one piece of text, for handlers that send in bulk."""
        ...
