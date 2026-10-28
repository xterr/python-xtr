"""Slack for xtr-notifier: chat messages posted, scheduled and updated in a channel.

Install it beside xtr-notifier and a ``slack://TOKEN@default?channel=CHANNEL`` DSN is
served by :class:`SlackTransportFactory` with no wiring. Build a message's options with
:class:`SlackOptions` and the blocks of :mod:`.block`; update a posted message through
the :class:`SlackSentMessage` the transport returns.
"""

from __future__ import annotations

from .slack_options import SlackOptions
from .slack_sent_message import SlackSentMessage
from .slack_transport import SlackTransport
from .slack_transport_factory import SlackTransportFactory
from .update_message_slack_options import UpdateMessageSlackOptions

__all__ = [
    "SlackOptions",
    "SlackSentMessage",
    "SlackTransport",
    "SlackTransportFactory",
    "UpdateMessageSlackOptions",
]
