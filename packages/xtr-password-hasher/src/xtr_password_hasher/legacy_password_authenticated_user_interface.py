"""A user whose password hash needs a salt stored beside it."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .password_authenticated_user_interface import PasswordAuthenticatedUserInterface

__all__ = ["LegacyPasswordAuthenticatedUserInterface"]


@runtime_checkable
class LegacyPasswordAuthenticatedUserInterface(PasswordAuthenticatedUserInterface, Protocol):
    """A user whose password was hashed under a salt it keeps separately.

    The user password hasher hands the salt to a
    :class:`~xtr_password_hasher.LegacyPasswordHasherInterface`. Once every
    stored hash has been upgraded to a self-salting algorithm, implement
    :class:`~xtr_password_hasher.PasswordAuthenticatedUserInterface` instead.
    """

    def get_salt(self) -> str | None:
        """Return the salt the password was originally hashed with, or ``None``."""
        ...
