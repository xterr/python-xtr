"""What hands out the hasher a given user, class or name should use."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_password_hasher.password_hasher_interface import PasswordHasherInterface

__all__ = ["PasswordHasherFactoryInterface"]


@runtime_checkable
class PasswordHasherFactoryInterface(Protocol):
    """Resolves which hasher a user, a class or a name is hashed by.

    One application may hash different users differently — a slow argon2 for
    people, a cheap one for machine accounts — so the hasher is chosen per
    user, not fixed once.
    """

    def get_password_hasher(self, user: str | type | object) -> PasswordHasherInterface:
        """Return the hasher for ``user``.

        Args:
            user: A user instance, a user class, or a name string.

        Raises:
            UnknownPasswordHasherError: When nothing is configured for it.
        """
        ...
