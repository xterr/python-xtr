"""The root every caching error derives from."""

from __future__ import annotations

__all__ = ["CacheError"]


class CacheError(Exception):
    """Base class for every error raised through the caching contract.

    Catch this to handle anything caching can go wrong with, whichever
    package raised it; catch a subclass to handle one cause. Every subclass
    carries the data a caller needs as typed attributes and composes its own
    message from them.

    A backend failing is not one of those causes: a cache is an optimisation,
    so a pool reports a backend it cannot reach by returning ``False`` rather
    than by raising. What does raise is a mistake in the calling code — a key
    no pool accepts, a tag on an item that cannot carry one.
    """
