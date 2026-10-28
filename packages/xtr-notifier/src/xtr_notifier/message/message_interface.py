"""What a transport sends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .message_options import MessageOptions

__all__ = ["MessageInterface"]


@runtime_checkable
class MessageInterface(Protocol):
    """A message a transport sends: a chat message, a text message, a push notification."""

    @property
    def recipient_id(self) -> str | None:
        """Who the message goes to on the provider, or ``None`` for the transport's default."""
        ...

    @property
    def subject(self) -> str:
        """The text every provider shows."""
        ...

    @property
    def options(self) -> MessageOptions | None:
        """The provider's options, or ``None`` for its defaults."""
        ...

    @property
    def transport(self) -> str | None:
        """The name of the transport to send through, or ``None`` for the first that can."""
        ...
