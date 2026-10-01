"""Hashing and verifying a password against the user it belongs to."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .password_hasher_factory_interface import (
    PasswordHasherFactoryInterface,  # noqa: TC001 — container hydrates this constructor at runtime
)
from .user_password_hasher_interface import UserPasswordHasherInterface

if TYPE_CHECKING:
    from xtr_password_hasher.password_authenticated_user_interface import (
        PasswordAuthenticatedUserInterface,
    )

__all__ = ["UserPasswordHasher"]


@final
class UserPasswordHasher(UserPasswordHasherInterface):
    """Hashes and checks a password for a user, using the hasher its factory chooses.

    Every call resolves the user's hasher through the factory, so one
    application can hash different users differently while callers only ever
    hand over the user and the plaintext.
    """

    __slots__ = ("_factory",)

    def __init__(self, factory: PasswordHasherFactoryInterface) -> None:
        """Resolve each user's hasher through ``factory``."""
        self._factory = factory

    @override
    def hash_password(self, user: PasswordAuthenticatedUserInterface, plain: str) -> str:
        """Hash ``plain`` with the hasher chosen for ``user``.

        Raises:
            InvalidPasswordError: When ``plain`` is too long.
            UnknownPasswordHasherError: When no hasher is configured for the user.
        """
        return self._factory.get_password_hasher(user).hash(plain)

    @override
    def is_password_valid(self, user: PasswordAuthenticatedUserInterface, plain: str) -> bool:
        """Return whether ``plain`` matches ``user``'s stored password.

        Raises:
            UnknownPasswordHasherError: When no hasher is configured for the user.
        """
        hashed = user.get_password()
        if hashed is None:
            return False
        return self._factory.get_password_hasher(user).verify(hashed, plain)

    @override
    def needs_rehash(self, user: PasswordAuthenticatedUserInterface) -> bool:
        """Return whether ``user``'s stored password should be rehashed.

        Raises:
            UnknownPasswordHasherError: When no hasher is configured for the user.
        """
        hashed = user.get_password()
        if hashed is None:
            return False
        return self._factory.get_password_hasher(user).needs_rehash(hashed)
