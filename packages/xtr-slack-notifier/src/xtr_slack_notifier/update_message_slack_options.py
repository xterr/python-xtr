"""Options that update a Slack message already posted."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from .slack_options import SlackOptions

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["UpdateMessageSlackOptions"]


@final
class UpdateMessageSlackOptions(SlackOptions):
    """The options of an update to the message posted at ``ts`` in a channel.

    They render with the kind ``slack.update``: once rendered, options are
    plain data that can cross a message bus, so the kind — not the builder's
    class — is what tells the transport to call ``chat.update``.
    """

    KIND: ClassVar[str] = "slack.update"

    __slots__: ClassVar[tuple[str, ...]] = ()

    def __init__(
        self, channel_id: str, message_id: str, options: Mapping[str, object] | None = None
    ) -> None:
        """Update the message ``message_id`` (its ``ts``) in ``channel_id``, with ``options``."""
        super().__init__({**(options or {}), "channel": channel_id, "ts": message_id})
