"""A notification that renders its own chat message."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_notifier.message.chat_message import ChatMessage
    from xtr_notifier.recipient import RecipientInterface

__all__ = ["ChatNotificationInterface"]


@runtime_checkable
class ChatNotificationInterface(Protocol):
    """A notification that says what the chat channel sends, instead of the default message.

    Implement it on a :class:`~xtr_notifier.notification.Notification`
    subclass to attach provider options or reword the text for one recipient
    or one transport; return ``None`` to fall back to the default.
    """

    def as_chat_message(
        self, recipient: RecipientInterface, transport_name: str | None
    ) -> ChatMessage | None:
        """Return the message for ``recipient`` through ``transport_name``, or ``None``.

        Args:
            recipient: Who the message goes to.
            transport_name: The transport the channel was asked for (``"slack"``
                in ``"chat/slack"``), or ``None`` for whichever supports it.
        """
        ...
