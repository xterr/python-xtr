"""Somewhere a rehashed password can be written back."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_password_hasher import PasswordAuthenticatedUserInterface

__all__ = ["PasswordUpgraderInterface"]


@runtime_checkable
class PasswordUpgraderInterface(Protocol):
    """Persists a freshly rehashed password for a user.

    A user store implements this so a password verified against an outdated
    hash is quietly re-stored under the current algorithm — an opportunistic
    upgrade that happens on a successful login and nowhere else.

    The upgrade is best-effort: it runs after the user is already
    authenticated, so it must not raise. A store that cannot write the new hash
    swallows the failure — the login still succeeds; the hash is upgraded on
    the next login instead.
    """

    async def upgrade_password(
        self,
        user: PasswordAuthenticatedUserInterface,
        new_hashed_password: str,
    ) -> None:
        """Store ``new_hashed_password`` for ``user``; never raise on failure."""
        ...
