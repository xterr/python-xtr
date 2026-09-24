"""A handler's channel list mixes included and excluded channels."""

from __future__ import annotations

from .logging_error import LoggingError

__all__ = ["MixedChannelFilterError"]


class MixedChannelFilterError(LoggingError, ValueError):
    """A handler's channel list mixes included (``foo``) and excluded (``!foo``) channels.

    "Only ``foo``" and "all but ``bar``"
    cannot both be true, and guessing which was meant routes records wrongly.
    A :class:`ValueError` too, so a configuration parser reports where it is.
    """

    channels: tuple[str, ...]

    def __init__(self, channels: tuple[str, ...]) -> None:
        """Record the list that mixes both forms."""
        self.channels = channels
        super().__init__(
            f"channels {list(channels)!r} mix included and excluded channels; use one form",
        )
