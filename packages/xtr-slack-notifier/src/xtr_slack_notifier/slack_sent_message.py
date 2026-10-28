"""What the Slack transport reports about a message it posted."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_notifier.message import ChatMessage, SentMessage

from .update_message_slack_options import UpdateMessageSlackOptions

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_notifier.message import MessageInterface

__all__ = ["SlackSentMessage"]


@final
class SlackSentMessage(SentMessage):
    """A posted message, with the channel and the ``ts`` that identify it for an update."""

    __slots__ = ("_channel_id",)

    def __init__(
        self, original: MessageInterface, transport: str, channel_id: str, message_id: str
    ) -> None:
        """Record ``original``, posted through ``transport`` to ``channel_id`` at ``message_id``."""
        super().__init__(original, transport, message_id=message_id)
        self._channel_id = channel_id

    @property
    def channel_id(self) -> str:
        """The id of the channel the message was posted to."""
        return self._channel_id

    def get_update_message(
        self, subject: str, options: Mapping[str, object] | None = None
    ) -> ChatMessage:
        """Return the message updating this one to ``subject``, with ``options``."""
        return ChatMessage(
            subject,
            UpdateMessageSlackOptions(self._channel_id, str(self.message_id), options).to_options(),
        )
