"""Telegram for xtr-notifier: chat messages sent, edited and answered through a bot.

Install it beside xtr-notifier and a ``telegram://BOT_ID:TOKEN@default?channel=CHAT_ID``
DSN is served by :class:`TelegramTransportFactory` with no wiring. Build a message's
options with :class:`TelegramOptions` — keyboards from :mod:`.reply.markup`, media, an
edit of an earlier message, a callback query's answer.
"""

from __future__ import annotations

from .telegram_options import TelegramOptions
from .telegram_transport import TelegramTransport
from .telegram_transport_factory import TelegramTransportFactory

__all__ = ["TelegramOptions", "TelegramTransport", "TelegramTransportFactory"]
