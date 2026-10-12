"""A value handed to this library cannot be used."""

from __future__ import annotations

from .remote_event_error import RemoteEventError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(RemoteEventError, ValueError):
    """A value handed to this library cannot be used: a consumer name, a payload.

    Also a :class:`ValueError`, so code that already guards what it was given
    with ``except ValueError`` keeps working without learning a new exception.
    """
