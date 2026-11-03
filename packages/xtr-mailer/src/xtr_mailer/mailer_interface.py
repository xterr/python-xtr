"""What application code sends email through."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_mime import RawMessage

    from .envelope import Envelope

__all__ = ["MailerInterface"]


@runtime_checkable
class MailerInterface(Protocol):
    """Sends an email now, or queues it on a message bus for a worker to send.

    Code sending email depends on this rather than on a transport: whether the email leaves
    in this process or in a worker is the application's configuration, not the caller's.
    """

    async def send(self, message: RawMessage, envelope: Envelope | None = None) -> None:
        """Send or queue ``message`` with ``envelope``, or the envelope its headers give.

        Raises:
            TransportError: The email was sent now, or by a handler of the bus in this
                process, and the server could not be reached or refused it.
        """
        ...
