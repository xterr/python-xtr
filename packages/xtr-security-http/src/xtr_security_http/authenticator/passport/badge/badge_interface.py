"""What a badge — a single fact a passport carries — answers to."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["BadgeInterface"]


@runtime_checkable
class BadgeInterface(Protocol):
    """One fact about an authentication, resolved before a token is made.

    A passport is a bag of badges: the user's identifier, the password to
    verify, a note that a password should be upgraded. Each badge starts
    unresolved and is marked resolved by whoever handles it — a listener on the
    passport-check event, or the badge itself when it needs nothing. Every
    badge must report itself resolved by the time the check is done, or
    authentication fails.
    """

    def is_resolved(self) -> bool:
        """Tell whether this badge has been handled and needs nothing more."""
        ...
