"""Building what a Slack message carries beyond its text."""

from __future__ import annotations

import copy
from collections.abc import Sized
from typing import TYPE_CHECKING, ClassVar, Final, Self, cast

from typing_extensions import override
from xtr_notifier.exception import LogicError
from xtr_notifier.message import MessageOptions, MessageOptionsInterface

from .block import SlackDividerBlock, SlackSectionBlock

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from xtr_notifier.notification import NotificationSummary

    from .block import SlackBlockInterface

__all__ = ["SlackOptions"]

_MAX_BLOCKS: Final = 50
_TOO_MANY_BLOCKS: Final = f'Maximum number of "blocks" has been reached ({_MAX_BLOCKS}).'


class SlackOptions(MessageOptionsInterface):
    """The options of a Slack message, one fluent call at a time.

    Each method sets a field of ``chat.postMessage``, and :meth:`to_options`
    renders them, in the order they were set, as the
    :class:`~xtr_notifier.message.MessageOptions` a message carries. Setting
    ``post_at`` schedules the message instead of posting it.

    Not final: :class:`~xtr_slack_notifier.UpdateMessageSlackOptions` renders
    the same fields as an update of a message already posted.
    """

    #: The ``kind`` these options render with, which tells the transport what to call.
    KIND: ClassVar[str] = "slack"

    __slots__: ClassVar[tuple[str, ...]] = ("_options",)

    def __init__(self, options: Mapping[str, object] | None = None) -> None:
        """Start from ``options``, the Web API's fields, plus ``recipient_id`` for the channel.

        Raises:
            LogicError: When ``options`` holds more than 50 blocks.
        """
        self._options: dict[str, object] = copy.deepcopy(dict(options or {}))
        if self._block_count() > _MAX_BLOCKS:
            raise LogicError(_TOO_MANY_BLOCKS)

    @classmethod
    def from_notification(cls, notification: NotificationSummary) -> SlackOptions:
        """Render ``notification``: its emoji as the icon, its subject, content and exception.

        The exception's traceback follows a divider, as a section of its own.
        """
        options = cls().icon_emoji(notification.emoji)
        _ = options.block(SlackSectionBlock().text(notification.subject))
        if notification.content:
            _ = options.block(SlackSectionBlock().text(notification.content))
        if notification.exception_as_string:
            _ = options.block(SlackDividerBlock())
            _ = options.block(SlackSectionBlock().text(notification.exception_as_string))
        return options

    @property
    @override
    def recipient_id(self) -> str | None:
        """The channel the message goes to, or ``None`` for the transport's channel."""
        recipient = self._options.get("recipient_id")
        return None if recipient is None else str(recipient)

    @override
    def to_options(self) -> MessageOptions:
        """Render the fields set so far — a copy, so later calls do not change it."""
        values = copy.deepcopy(self._options)
        _ = values.pop("recipient_id", None)
        return MessageOptions(self.KIND, self.recipient_id, values)

    def recipient(self, recipient_id: str) -> Self:
        """Post to the channel or user ``recipient_id`` rather than the transport's channel."""
        self._options["recipient_id"] = recipient_id
        return self

    def as_user(self, as_user: bool) -> Self:
        """Post as the authenticated user rather than as the app."""
        self._options["as_user"] = as_user
        return self

    def post_at(self, timestamp: datetime) -> Self:
        """Schedule the message for ``timestamp`` instead of posting it now."""
        self._options["post_at"] = int(timestamp.timestamp())
        return self

    def block(self, block: SlackBlockInterface) -> Self:
        """Add ``block`` to the message's layout.

        Raises:
            LogicError: When the message already has 50 blocks.
        """
        if self._block_count() >= _MAX_BLOCKS:
            raise LogicError(_TOO_MANY_BLOCKS)
        existing = self._options.get("blocks")
        blocks = list(cast("list[object]", existing)) if isinstance(existing, list) else []
        blocks.append(block.to_array())
        self._options["blocks"] = blocks
        return self

    def icon_emoji(self, emoji: str) -> Self:
        """Show ``emoji`` as the poster's icon."""
        self._options["icon_emoji"] = emoji
        return self

    def icon_url(self, url: str) -> Self:
        """Show the image at ``url`` as the poster's icon."""
        self._options["icon_url"] = url
        return self

    def link_names(self, link_names: bool) -> Self:
        """Turn ``@names`` and ``#channels`` in the text into links."""
        self._options["link_names"] = link_names
        return self

    def mrkdwn(self, mrkdwn: bool) -> Self:
        """Read the text as Slack's markup, or as plain text."""
        self._options["mrkdwn"] = mrkdwn
        return self

    def parse(self, parse: str) -> Self:
        """Set how the text is parsed: ``full`` or ``none``."""
        self._options["parse"] = parse
        return self

    def unfurl_links(self, unfurl: bool) -> Self:
        """Preview the text's links to articles and pages."""
        self._options["unfurl_links"] = unfurl
        return self

    def unfurl_media(self, unfurl: bool) -> Self:
        """Preview the text's links to media."""
        self._options["unfurl_media"] = unfurl
        return self

    def username(self, username: str) -> Self:
        """Post under ``username``."""
        self._options["username"] = username
        return self

    def thread_ts(self, thread_ts: str) -> Self:
        """Reply in the thread of the message posted at ``thread_ts``."""
        self._options["thread_ts"] = thread_ts
        return self

    def _block_count(self) -> int:
        """Return how many blocks are set."""
        blocks = self._options.get("blocks")
        return len(blocks) if isinstance(blocks, Sized) else 0
