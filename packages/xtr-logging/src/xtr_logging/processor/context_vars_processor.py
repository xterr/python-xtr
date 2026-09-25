"""Merges the ambient context bound in this thread or task into each record."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_logging.log_context import current_context

from .processor_interface import ProcessorInterface

if TYPE_CHECKING:
    from xtr_logging.log_record import LogRecord

__all__ = ["ContextVarsProcessor"]


@final
class ContextVarsProcessor(ProcessorInterface):
    """Copies whatever :func:`~xtr_logging.log_context.bind_context` bound into ``extra``.

    Fields bound for the current request or task — a request id, the user —
    ride along on every record without being passed to each logging call. With
    a ``key`` they are nested under ``extra[key]``; without one they are merged
    in flat. An empty ambient context adds nothing.
    """

    __slots__ = ("_key",)

    def __init__(self, key: str | None = None) -> None:
        """Nest the bound values under ``key``, or merge them in flat when ``None``."""
        self._key: str | None = key

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record`` with the ambient context in ``extra``, if there is any."""
        ambient = current_context()
        if not ambient:
            return record
        if self._key is None:
            return record.with_extra(ambient)
        return record.with_extra({self._key: dict(ambient)})
