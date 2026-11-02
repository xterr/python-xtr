"""The database refused what a transport asked of it."""

from __future__ import annotations

from .orm_messenger_error import OrmMessengerError

__all__ = ["TransportError"]


class TransportError(OrmMessengerError):
    """The database refused what a transport asked of it.

    Raised from the driver's own error, which stays the cause, so nothing it
    said is lost. The message names the transport and the operation, never the
    connection's URL, whose credentials a traceback would otherwise carry.

    Attributes:
        transport: The transport the operation was for.
        operation: What was asked — ``send``, ``get``, ``ack``, ...
        reason: What went wrong.
    """

    transport: str
    operation: str
    reason: str

    def __init__(self, transport: str, operation: str, reason: str) -> None:
        """Record which transport failed, at what, and why."""
        self.transport = transport
        self.operation = operation
        self.reason = reason
        super().__init__(f'The "{transport}" transport could not {operation}: {reason}.')
