"""The events dispatched around each email a transport sends or the mailer queues.

:class:`MessageEvent` comes before an email is sent or queued, and lets a listener change,
reject or stamp it; :class:`SentMessageEvent` and :class:`FailedMessageEvent` come after a
transport tried. :class:`MessageEvents` keeps what was seen, for tests.
"""

from __future__ import annotations

from .failed_message_event import FailedMessageEvent
from .message_event import MessageEvent
from .message_events import MessageEvents
from .sent_message_event import SentMessageEvent

__all__ = ["FailedMessageEvent", "MessageEvent", "MessageEvents", "SentMessageEvent"]
