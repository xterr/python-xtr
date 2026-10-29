"""A configuration value the makers cannot work with."""

from __future__ import annotations

from .maker_error import MakerError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(MakerError, ValueError):
    """A configuration value the makers cannot work with.

    Also a :class:`ValueError`, so code catching that keeps working.
    """
