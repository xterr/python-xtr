"""Something the notifier depends on failed while it was sending."""

from __future__ import annotations

from .notifier_error import NotifierError

__all__ = ["NotifierRuntimeError"]


class NotifierRuntimeError(NotifierError, RuntimeError):
    """Something a notification depends on failed while it was sent — every transport, say.

    The input was fine and the code is fine; the world did not cooperate. Raising
    one out of a message handler is what makes a message bus retry the send.
    """
