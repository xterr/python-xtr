"""What hashes and checks a password against the user it belongs to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_password_hasher.password_authenticated_user_interface import (
        PasswordAuthenticatedUserInterface,
    )

__all__ = ["UserPasswordHasherInterface"]


@runtime_checkable
class UserPasswordHasherInterface(Protocol):
    """Hashes and verifies a password for a user, choosing the hasher by the user.

    A thin seam over the factory: it picks the right hasher for the user's
    class or declared name, so callers hand it the user and the plaintext and
    never touch a hasher directly.
    """

    def hash_password(self, user: PasswordAuthenticatedUserInterface, plain: str) -> str:
        """Hash ``plain`` with the hasher chosen for ``user``.

        Raises:
            InvalidPasswordError: When ``plain`` is too long.
            UnknownPasswordHasherError: When no hasher is configured for the user.
        """
        ...

    def is_password_valid(self, user: PasswordAuthenticatedUserInterface, plain: str) -> bool:
        """Return whether ``plain`` matches ``user``'s stored password.

        ``False`` when the user carries no password, so there is nothing to
        match against.

        Raises:
            UnknownPasswordHasherError: When no hasher is configured for the user.
        """
        ...

    def needs_rehash(self, user: PasswordAuthenticatedUserInterface) -> bool:
        """Return whether ``user``'s stored password should be rehashed.

        ``False`` when the user carries no password.

        Raises:
            UnknownPasswordHasherError: When no hasher is configured for the user.
        """
        ...
