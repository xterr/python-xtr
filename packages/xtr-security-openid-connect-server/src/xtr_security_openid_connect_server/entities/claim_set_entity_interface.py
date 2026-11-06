"""What a claim set answers to."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["ClaimSetEntityInterface"]


@runtime_checkable
class ClaimSetEntityInterface(Protocol):
    """The claims one scope reveals about the user who granted it.

    A scope is a permission; a claim set says which of a user's claims that
    permission opens up — ``email`` opens ``email`` and ``email_verified``,
    say. Only two things are read off a set: the scope, matched against the
    scopes a token was granted, and the claim names, picked out of what the
    user holds. Where an application keeps its sets — a constant, its
    configuration, a table — stays on its own class.
    """

    def get_scope(self) -> str:
        """Return the scope whose grant reveals these claims."""
        ...

    def get_claim_names(self) -> tuple[str, ...]:
        """Return the names of the claims the scope reveals, in the order declared."""
        ...
