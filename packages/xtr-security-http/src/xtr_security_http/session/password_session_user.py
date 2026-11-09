"""The stand-in a session rebuilds for a password-carrying user it kept a snapshot of."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_password_hasher import PasswordAuthenticatedUserInterface

from .session_user import SessionUser

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["PasswordSessionUser"]


@final
class PasswordSessionUser(SessionUser, PasswordAuthenticatedUserInterface):
    """A session's snapshot of a user that carried a password, with its digest.

    The snapshot keeps the
    :func:`~xtr_security_core.user.password_digest.password_digest` of the
    password, never the hash, and :meth:`get_password` answers that digest:
    the comparison weighing the reload reads a stored password of eight
    characters that is the digest of the reloaded one as the same password,
    so the user stays signed in until the password really changes.
    """

    __slots__: tuple[str, ...] = ("_password",)

    _password: str | None

    def __init__(self, identifier: str, roles: Sequence[str], password: str | None) -> None:
        """Record who the user was, the roles it held, and its password's digest.

        Args:
            identifier: The identifier the user was kept under.
            roles: The roles the user held.
            password: The digest of the user's password, or ``None`` when the
                user carried none.

        Raises:
            InvalidArgumentError: When ``identifier`` is empty.
        """
        super().__init__(identifier, roles)
        self._password = password

    @override
    def get_password(self) -> str | None:
        """Return the digest of the user's password, or ``None`` when it carried none."""
        return self._password
