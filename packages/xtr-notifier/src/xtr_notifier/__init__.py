"""Notifications sent to chat, SMS and push channels.

A notification says what happened and how much it matters. The notifier picks the channels
it goes to — from the notification itself or from a policy keyed by its importance — and each
channel hands a message to a transport configured by DSN, or to a message bus.
"""

from __future__ import annotations

from .chatter import Chatter
from .chatter_interface import ChatterInterface
from .texter import Texter
from .texter_interface import TexterInterface
from .transport import Transport

__all__ = ["Chatter", "ChatterInterface", "Texter", "TexterInterface", "Transport"]
