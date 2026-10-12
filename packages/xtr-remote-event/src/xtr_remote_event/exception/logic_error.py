"""This library was used in a way that cannot work."""

from __future__ import annotations

from .remote_event_error import RemoteEventError

__all__ = ["LogicError"]


class LogicError(RemoteEventError, RuntimeError):
    """This library was asked for something no input could make right.

    An event arriving for a source nothing is registered under is the case
    this exists for: the payload was fine, the application simply has no
    consumer for it — a wiring mistake, not a bad request.

    Also a :class:`RuntimeError`, because that is what a worker's own
    error handling already catches.
    """
