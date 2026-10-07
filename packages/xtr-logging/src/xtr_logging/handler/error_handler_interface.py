"""What a queue handler hands a record its wrapped handler failed on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_logging.log_record import LogRecord

__all__ = ["ErrorHandlerInterface"]


@runtime_checkable
class ErrorHandlerInterface(Protocol):
    """Receives a failure the queue handler's worker caught, and the record behind it.

    The worker must outlive a broken handler, so it cannot let the exception
    rise; it reports it here instead. A plain function with this signature is
    one: register it as a service of this type under the id a queue handler's
    ``on_error`` names.
    """

    def __call__(self, error: Exception, record: LogRecord, /) -> None:
        """Report ``error``, raised while handling ``record``."""
        ...
