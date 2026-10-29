"""A processor limited to one channel: ``@as_processor(channel=...)``."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_logging import LogRecord, ProcessorInterface, as_processor

__all__ = ["OrdersComponentProcessor"]


@final
@as_processor(channel="orders", priority=10)
class OrdersComponentProcessor(ProcessorInterface):
    """Only the ``orders`` channel."""

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        return record.with_extra({"component": "ordering"})
