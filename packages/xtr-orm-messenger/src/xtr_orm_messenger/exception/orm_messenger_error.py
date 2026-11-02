"""The root every error in this library derives from."""

from __future__ import annotations

from xtr_messenger import MessageBusError

__all__ = ["OrmMessengerError"]


class OrmMessengerError(MessageBusError):
    """Base class for every error raised by this library.

    Also a :class:`~xtr_messenger.MessageBusError`, so code catching what the
    bus can go wrong with catches this transport's failures too.
    """
