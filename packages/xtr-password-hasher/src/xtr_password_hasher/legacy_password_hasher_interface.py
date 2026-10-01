"""What a hasher whose salt is stored outside the hash answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from typing_extensions import override

from .password_hasher_interface import PasswordHasherInterface

if TYPE_CHECKING:
    from typing import TypeGuard

__all__ = ["LegacyPasswordHasherInterface", "is_legacy_password_hasher"]


@runtime_checkable
class LegacyPasswordHasherInterface(PasswordHasherInterface, Protocol):
    """A hasher that takes its salt from the caller rather than minting one.

    Older schemes store the salt in a column of its own and the bare digest in
    another; the hash alone cannot be verified. Such a hasher is kept to read
    those hashes and upgrade them — new passwords belong to a self-salting
    hasher. A ``None`` salt means no salt at all.

    Every method name matches :class:`PasswordHasherInterface`, so an
    ``isinstance`` check cannot tell the two apart; ask
    :func:`is_legacy_password_hasher` instead.
    """

    @override
    def hash(self, plain_password: str, salt: str | None = None) -> str:
        """Hash ``plain_password`` under ``salt``.

        Raises:
            InvalidPasswordError: When ``plain_password`` is longer than
                :data:`~xtr_password_hasher.MAX_PASSWORD_LENGTH`.
        """
        ...

    @override
    def verify(self, hashed_password: str, plain_password: str, salt: str | None = None) -> bool:
        """Return whether ``plain_password`` under ``salt`` made ``hashed_password``."""
        ...


def is_legacy_password_hasher(
    hasher: PasswordHasherInterface,
) -> TypeGuard[LegacyPasswordHasherInterface]:
    """Return whether ``hasher`` declares :class:`LegacyPasswordHasherInterface`.

    The check is by inheritance, not by shape: a structural match would accept
    every hasher, since the two interfaces share their method names and differ
    only in the ``salt`` parameter.
    """
    return LegacyPasswordHasherInterface in type(hasher).__mro__
