"""A hasher that does not hash — for tests only."""

from __future__ import annotations

import hmac
from typing import final

from typing_extensions import override

from xtr_password_hasher.password_hasher_interface import PasswordHasherInterface

from ._password_length import ensure_within_length, is_within_length

__all__ = ["PlaintextPasswordHasher"]


@final
class PlaintextPasswordHasher(PasswordHasherInterface):
    """Stores the password as it is; verifies by constant-time comparison.

    For tests and fixtures, never production: the "hash" is the plaintext. It
    exists so a test suite can run without paying argon2's cost, and so a
    migrating hasher can read fixtures stored in the clear.
    """

    __slots__ = ()

    @override
    def hash(self, plain: str) -> str:
        """Return ``plain`` unchanged, after the shared length guard.

        Raises:
            InvalidPasswordError: When ``plain`` is too long.
        """
        ensure_within_length(plain)
        return plain

    @override
    def verify(self, hashed: str, plain: str) -> bool:
        """Return whether ``plain`` equals ``hashed``, in constant time."""
        if not is_within_length(plain):
            return False
        return hmac.compare_digest(hashed.encode("utf-8"), plain.encode("utf-8"))

    @override
    def needs_rehash(self, hashed: str) -> bool:
        """Return ``False``: a plaintext store has nothing to upgrade to."""
        del hashed
        return False
