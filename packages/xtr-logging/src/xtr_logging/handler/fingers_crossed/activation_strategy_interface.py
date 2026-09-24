"""What tells a fingers-crossed handler the request has gone wrong."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_logging.log_record import LogRecord

__all__ = ["ActivationStrategyInterface"]


@runtime_checkable
class ActivationStrategyInterface(Protocol):
    """Decides, from a single record, whether buffering should stop and flush.

    A fingers-crossed handler holds everything back until something worth
    keeping happens. The strategy is that judgement, kept apart from the
    handler so the same handler can trigger on an error level, on a per-channel
    level, or on anything else a caller can express.
    """

    def is_handler_activated(self, record: LogRecord, /) -> bool:
        """Whether ``record`` is the one that should release the buffer."""
        ...
