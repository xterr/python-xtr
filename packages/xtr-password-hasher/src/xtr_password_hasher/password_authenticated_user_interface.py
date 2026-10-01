"""A user that carries a hashed password."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["PasswordAuthenticatedUserInterface"]


@runtime_checkable
class PasswordAuthenticatedUserInterface(Protocol):
    """A user whose identity can be proven by a password.

    The hasher factory keys on this: a user that carries a password is hashed
    and verified by whichever hasher its class is mapped to. The password is
    the stored hash, not the plaintext — ``None`` when the user has no password
    and so cannot authenticate by one.
    """

    def get_password(self) -> str | None:
        """Return the stored password hash, or ``None`` when there is none."""
        ...
