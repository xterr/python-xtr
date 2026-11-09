"""The stand-in a session rebuilds for a user it could only keep a snapshot of."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.user_interface import UserInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["SessionUser"]


class SessionUser(UserInterface):
    """Who a session's user was, and the roles it held — and nothing more.

    A session holds JSON, and a user that cannot turn itself into JSON is kept
    as a snapshot instead: its identifier and its roles. This is what the
    snapshot is rebuilt as, so the request that reads the session knows who to
    reload — the firewall's providers load the user by this identifier, and
    this stand-in is never handed to one as a user of its own.

    A user that carried a password is rebuilt as the
    :class:`~xtr_security_http.session.password_session_user.PasswordSessionUser`
    subclass instead, so the comparison weighing the reload still sees which
    side stopped carrying one.
    """

    __slots__: tuple[str, ...] = ("_identifier", "_roles")

    _identifier: str
    _roles: tuple[str, ...]

    def __init__(self, identifier: str, roles: Sequence[str]) -> None:
        """Record who the user was and the roles it held.

        Raises:
            InvalidArgumentError: When ``identifier`` is empty.
        """
        if identifier == "":
            raise InvalidArgumentError("A session user's identifier cannot be empty.")
        self._identifier = identifier
        self._roles = tuple(roles)

    @override
    def get_user_identifier(self) -> str:
        """Return the identifier the user was kept under."""
        return self._identifier

    @override
    def get_roles(self) -> Sequence[str]:
        """Return the roles the user held when it was kept."""
        return self._roles
