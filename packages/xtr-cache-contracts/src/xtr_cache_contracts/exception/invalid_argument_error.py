"""A cache was given a key, a tag or an option it cannot work with."""

from __future__ import annotations

from .cache_error import CacheError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(CacheError, ValueError):
    """A cache was given a key, a tag or an option it cannot work with.

    An empty key, one holding a reserved character, a negative ``beta``.
    Raised where the argument is given, before anything reaches a backend.

    Also a :class:`ValueError`, so code that already guards its input with
    ``except ValueError`` keeps working without learning a new exception.

    Attributes:
        reason: What is wrong with the argument.
    """

    reason: str

    def __init__(self, reason: str) -> None:
        """Record what is wrong with the argument."""
        self.reason = reason
        super().__init__(reason)
