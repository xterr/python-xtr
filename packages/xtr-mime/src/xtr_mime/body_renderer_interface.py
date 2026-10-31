"""What fills in a message's body before it is sent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .message import Message

__all__ = ["BodyRendererInterface"]


@runtime_checkable
class BodyRendererInterface(Protocol):
    """Renders the body of a message from what it carries — a template and its data, say.

    The mailer calls it on each message before the message is sent, so the body is built
    once, where the data it needs is at hand.
    """

    def render(self, message: Message) -> None:
        """Fill in the body of ``message``, changing it in place."""
        ...
