"""A logger was asked for on a channel the configuration does not declare."""

from __future__ import annotations

from .logging_error import LoggingError

__all__ = ["UnknownChannelError"]


class UnknownChannelError(LoggingError):
    """A logger was asked for on a channel the configuration does not declare.

    Refused rather than created on the fly: a channel nobody declared has no
    handlers routed to it by name, so its records would go wherever the
    catch-all handlers send them — usually not where the caller expected.
    """

    channel: str
    known: tuple[str, ...]

    def __init__(self, channel: str, known: tuple[str, ...]) -> None:
        """Record the channel asked for, and those that exist."""
        self.channel = channel
        self.known = known
        super().__init__(f"channel {channel!r} is not declared; declared: {', '.join(known)}")
