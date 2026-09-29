"""A processor targets a channel or a handler, not both."""

from __future__ import annotations

from xtr_logging.exception.invalid_option_error import InvalidOptionError

__all__ = ["refuse_both_targets"]


def refuse_both_targets(channel: str | None, handler: str | None) -> None:
    """Refuse a processor aimed at both a channel and a handler.

    Raises:
        InvalidOptionError: If both are given.
    """
    if channel is not None and handler is not None:
        raise InvalidOptionError(
            "channel",
            channel,
            f"a processor targets a channel or a handler, not both (handler={handler})",
        )
