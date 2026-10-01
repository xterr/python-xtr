"""A hasher that does not hash — for tests only."""

from __future__ import annotations

import hmac
from typing import final

from typing_extensions import override

from xtr_password_hasher.exception import InvalidArgumentError
from xtr_password_hasher.legacy_password_hasher_interface import LegacyPasswordHasherInterface

from ._password_length import ensure_within_length, is_within_length

__all__ = ["PlaintextPasswordHasher"]


@final
class PlaintextPasswordHasher(LegacyPasswordHasherInterface):
    """Stores the password as it is; verifies by constant-time comparison.

    For tests and fixtures, never production: the "hash" is the plaintext,
    followed by ``{salt}`` when a salt is given. It exists so a test suite can
    run without paying argon2's cost. Never put it among a migrating hasher's
    extras: a leaked hash would then be a working password.
    """

    __slots__ = ("_ignore_password_case",)

    def __init__(self, ignore_password_case: bool = False) -> None:
        """Compare passwords case-insensitively when ``ignore_password_case`` is set."""
        self._ignore_password_case = ignore_password_case

    @override
    def hash(self, plain_password: str, salt: str | None = None) -> str:
        """Return ``plain_password``, merged with ``salt``, after the shared length guard.

        Raises:
            InvalidPasswordError: When ``plain_password`` is too long.
            InvalidArgumentError: When ``salt`` holds ``{`` or ``}``.
        """
        ensure_within_length(plain_password)
        return _merge(plain_password, salt)

    @override
    def verify(
        self,
        hashed_password: str,
        plain_password: str,
        salt: str | None = None,
    ) -> bool:
        """Return whether ``plain_password`` under ``salt`` equals ``hashed_password``.

        Raises:
            InvalidArgumentError: When ``salt`` holds ``{`` or ``}``.
        """
        if not is_within_length(plain_password):
            return False
        merged = _merge(plain_password, salt)
        if self._ignore_password_case:
            return hmac.compare_digest(hashed_password.lower().encode(), merged.lower().encode())
        return hmac.compare_digest(hashed_password.encode(), merged.encode())

    @override
    def needs_rehash(self, hashed_password: str) -> bool:
        """Return ``False``: a plaintext store has nothing to upgrade to."""
        del hashed_password
        return False


def _merge(plain_password: str, salt: str | None) -> str:
    """Append ``{salt}``, the braces marking where the password ends."""
    if not salt:
        return plain_password
    if "{" in salt or "}" in salt:
        raise InvalidArgumentError("Cannot use { or } in salt.")
    return f"{plain_password}{{{salt}}}"
