"""A message the null transport sent nowhere."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .message_interface import MessageInterface

if TYPE_CHECKING:
    from .message_options import MessageOptions

__all__ = ["NullMessage"]


@final
class NullMessage(MessageInterface):
    """A message as the null transport reports it: the same message, marked as sent nowhere.

    It reads through to the message it wraps, so a listener recording what was
    sent sees the subject and the recipient, while its type tells it nothing
    left the process.
    """

    __slots__ = ("_message",)

    def __init__(self, message: MessageInterface) -> None:
        """Wrap ``message``."""
        self._message = message

    @property
    def message(self) -> MessageInterface:
        """The message that was handed to the null transport."""
        return self._message

    @property
    @override
    def recipient_id(self) -> str | None:
        """The wrapped message's recipient."""
        return self._message.recipient_id

    @property
    @override
    def subject(self) -> str:
        """The wrapped message's subject."""
        return self._message.subject

    @property
    @override
    def options(self) -> MessageOptions | None:
        """The wrapped message's options."""
        return self._message.options

    @property
    @override
    def transport(self) -> str | None:
        """The wrapped message's transport name."""
        return self._message.transport
