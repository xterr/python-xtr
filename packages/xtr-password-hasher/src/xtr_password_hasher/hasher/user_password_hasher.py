"""Hashing and verifying a password against the user it belongs to."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_password_hasher.legacy_password_authenticated_user_interface import (
    LegacyPasswordAuthenticatedUserInterface,
)

from .migrating_password_hasher import hash_with_salt, verify_with_salt
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
    hand over the user and the plaintext. A
    :class:`~xtr_password_hasher.LegacyPasswordAuthenticatedUserInterface`
    user's salt goes to the hasher with the password.
    """

    __slots__ = ("_factory",)

    def __init__(self, factory: PasswordHasherFactoryInterface) -> None:
        """Resolve each user's hasher through ``factory``."""
        self._factory = factory

    @override
    def hash_password(self, user: PasswordAuthenticatedUserInterface, plain_password: str) -> str:
        """Hash ``plain_password`` with the hasher chosen for ``user``.

        Raises:
            InvalidPasswordError: When ``plain_password`` is too long.
            UnknownPasswordHasherError: When no hasher is configured for the user.
        """
        hasher = self._factory.get_password_hasher(user)
        return hash_with_salt(hasher, plain_password, _salt_of(user))

    @override
    def is_password_valid(
        self,
        user: PasswordAuthenticatedUserInterface,
        plain_password: str,
    ) -> bool:
        """Return whether ``plain_password`` matches ``user``'s stored password.

        A user whose stored password is ``None`` returns ``False`` at once,
        without hashing ``plain_password``. The early return is observable in
        time, so a caller that must not reveal which accounts have a password
        owns the timing guard — burning a dummy verify for the passwordless
        user, as the credentials listener does.

        Raises:
            UnknownPasswordHasherError: When no hasher is configured for the user.
        """
        hashed_password = user.get_password()
        if hashed_password is None:
            return False
        hasher = self._factory.get_password_hasher(user)
        return verify_with_salt(hasher, hashed_password, plain_password, _salt_of(user))

    @override
    def needs_rehash(self, user: PasswordAuthenticatedUserInterface) -> bool:
        """Return whether ``user``'s stored password should be rehashed.

        Raises:
            UnknownPasswordHasherError: When no hasher is configured for the user.
        """
        hashed_password = user.get_password()
        if hashed_password is None:
            return False
        return self._factory.get_password_hasher(user).needs_rehash(hashed_password)


def _salt_of(user: PasswordAuthenticatedUserInterface) -> str | None:
    if isinstance(user, LegacyPasswordAuthenticatedUserInterface):
        return user.get_salt()
    return None
