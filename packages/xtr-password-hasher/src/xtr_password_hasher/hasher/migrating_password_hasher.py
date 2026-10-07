"""A hasher that hashes with the best and verifies the legacy ones too."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_password_hasher.exception import InvalidArgumentError
from xtr_password_hasher.legacy_password_hasher_interface import is_legacy_password_hasher
from xtr_password_hasher.password_hasher_interface import PasswordHasherInterface

from .plaintext_password_hasher import PlaintextPasswordHasher

if TYPE_CHECKING:
    from typing import TypeGuard

    from xtr_password_hasher.legacy_password_hasher_interface import (
        LegacyPasswordHasherInterface,
    )

__all__ = ["MigratingPasswordHasher", "hash_with_salt", "verify_with_salt"]


@final
class MigratingPasswordHasher(PasswordHasherInterface):
    """Hashes with one preferred hasher, verifies with it and older ones behind it.

    A deployment holding hashes from several eras keeps this in front: new
    passwords are hashed with ``best``, and a stored hash ``best`` does not
    recognise is offered to each of ``extras`` in turn. A hash ``best`` already
    owns never reaches the extras, so the common path pays for one verify.

    A salt given to :meth:`hash` or :meth:`verify` is passed on to each hasher
    that takes one — a
    :class:`~xtr_password_hasher.LegacyPasswordHasherInterface`, or another
    migrating hasher — and left out for the self-salting ones, so a legacy
    salted hash verifies behind an argon2id front.

    Paired with :meth:`needs_rehash` — which delegates to ``best`` — a login
    verified against a legacy hash is the moment to rehash and upgrade it.
    Never put a :class:`~xtr_password_hasher.PlaintextPasswordHasher` among the
    extras: a leaked hash would then be a working password.
    """

    __slots__ = ("_best", "_extras")

    def __init__(
        self,
        best: PasswordHasherInterface,
        *extras: PasswordHasherInterface,
    ) -> None:
        """Hash with ``best``; fall back to ``extras`` only for hashes it disowns.

        Raises:
            InvalidArgumentError: When an extra is a
                :class:`~xtr_password_hasher.PlaintextPasswordHasher`; it
                "verifies" any string equal to the stored one, so behind a
                migrating hasher a leaked hash would be a working password.
        """
        for extra in extras:
            if isinstance(extra, PlaintextPasswordHasher):
                raise InvalidArgumentError(
                    "A PlaintextPasswordHasher must not be a MigratingPasswordHasher extra: "
                    "a leaked hash would then be a working password.",
                )
        self._best = best
        self._extras = extras

    @override
    def hash(self, plain_password: str, salt: str | None = None) -> str:
        """Hash ``plain_password`` with the preferred hasher.

        Raises:
            InvalidPasswordError: When ``plain_password`` is too long.
        """
        return hash_with_salt(self._best, plain_password, salt)

    @override
    def verify(
        self,
        hashed_password: str,
        plain_password: str,
        salt: str | None = None,
    ) -> bool:
        """Return whether ``plain_password`` made ``hashed_password``, best hasher first.

        When ``best`` recognises ``hashed_password`` — it does not need
        rehashing to the best format — only ``best`` verifies it. Otherwise each
        extra is tried, then ``best`` once more as a last resort.
        """
        if not self._best.needs_rehash(hashed_password):
            return verify_with_salt(self._best, hashed_password, plain_password, salt)
        for extra in self._extras:
            if verify_with_salt(extra, hashed_password, plain_password, salt):
                return True
        return verify_with_salt(self._best, hashed_password, plain_password, salt)

    @override
    def needs_rehash(self, hashed_password: str) -> bool:
        """Return whether ``hashed_password`` should be replaced, as the best hasher sees it."""
        return self._best.needs_rehash(hashed_password)


def _takes_salt(
    hasher: PasswordHasherInterface,
) -> TypeGuard[LegacyPasswordHasherInterface | MigratingPasswordHasher]:
    return is_legacy_password_hasher(hasher) or isinstance(hasher, MigratingPasswordHasher)


def hash_with_salt(hasher: PasswordHasherInterface, plain_password: str, salt: str | None) -> str:
    """Hash with ``hasher``, handing it ``salt`` only when it takes one."""
    if _takes_salt(hasher):
        return hasher.hash(plain_password, salt)
    return hasher.hash(plain_password)


def verify_with_salt(
    hasher: PasswordHasherInterface,
    hashed_password: str,
    plain_password: str,
    salt: str | None,
) -> bool:
    """Verify with ``hasher``, handing it ``salt`` only when it takes one."""
    if _takes_salt(hasher):
        return hasher.verify(hashed_password, plain_password, salt)
    return hasher.verify(hashed_password, plain_password)
