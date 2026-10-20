"""A message handed to a transport built for another kind."""

from __future__ import annotations

from .logic_error import LogicError

__all__ = ["UnsupportedMessageTypeError"]


class UnsupportedMessageTypeError(LogicError):
    """A transport was handed a message of a type it does not send — an SMS to a chat provider.

    Attributes:
        transport: The transport that refused the message.
        supported: The message type it sends.
        given: The name of the type it was handed.
    """

    transport: str
    supported: str
    given: str

    def __init__(self, transport: str, supported: str, given: object) -> None:
        """Name the transport, what it sends and what it was handed.

        Args:
            transport: The transport that refused the message.
            supported: The message type it sends.
            given: The message it was handed; only its type is reported.
        """
        self.transport = transport
        self.supported = supported
        self.given = type(given).__name__
        super().__init__(
            f'The "{transport}" transport only supports instances of "{supported}" '
            f'(instance of "{self.given}" given).'
        )
