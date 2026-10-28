"""Opening the reply box as if the user had chosen to reply."""

from __future__ import annotations

from typing import final

from .abstract_telegram_reply_markup import AbstractTelegramReplyMarkup

__all__ = ["ForceReply"]


@final
class ForceReply(AbstractTelegramReplyMarkup):
    """Shows the user a reply box for this message, as if they had tapped *Reply*."""

    def __init__(self, force_reply: bool = False, selective: bool = False) -> None:
        """Force the reply, for everyone or only the users the message mentions.

        Args:
            force_reply: Whether the reply box is opened.
            selective: Whether only the mentioned users, and the sender of the
                message replied to, get it.
        """
        super().__init__()
        self._options["force_reply"] = force_reply
        self._options["selective"] = selective
