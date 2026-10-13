"""A value handed to this library cannot be used."""

from __future__ import annotations

from .http_foundation_error import HttpFoundationError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(HttpFoundationError, ValueError):
    """A value handed to this library cannot be used: text that is not an address.

    Also a :class:`ValueError`, so code that already guards against a bad value
    catches it without knowing this library exists. It says a caller passed
    something it cannot have meant, which is why the checks that *decide* about a
    request — whether an address falls in a network — answer ``False`` instead of
    raising: an address that does not parse is simply not in the network.
    """
