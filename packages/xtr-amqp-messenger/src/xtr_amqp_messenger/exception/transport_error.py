"""The broker refused what a transport asked of it."""

from __future__ import annotations

from .amqp_messenger_error import AmqpMessengerError

__all__ = ["TransportError"]


class TransportError(AmqpMessengerError):
    """The broker refused what a transport asked of it, or could not be reached.

    Raised from the driver's own error, which stays the cause, so nothing it
    said is lost. The message names the transport and the operation, never the
    connection's URL, whose credentials a traceback would otherwise carry.

    Attributes:
        transport: The transport the operation was for.
        operation: What was asked — ``set up``, ``count messages``.
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
