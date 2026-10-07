"""A token built from a user's own roles to decide access away from a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .abstract_token import AbstractToken

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["OfflineToken"]


@final
class OfflineToken(AbstractToken):
    """A token standing in for a user who is not the current caller.

    :meth:`~xtr_security_core.authorization.authorization_checker.AuthorizationChecker.is_granted_for_user`
    builds one of these to decide access for a user elsewhere — a consent
    screen, a background worker. It carries the user and the roles fixed on it,
    so role checks decide the same way they would for the live caller; but a
    trust resolver treats it as *not* authenticated, because deciding on a
    user's behalf is not that user being present. Questions of authentication
    strength — ``IS_AUTHENTICATED``, ``IS_AUTHENTICATED_FULLY`` — are therefore
    denied against it.
    """

    __slots__: tuple[str, ...] = ()

    def __init__(self, user: UserInterface, roles: Sequence[str] = ()) -> None:
        """Record the user this token decides for, and the roles fixed on it."""
        super().__init__(user=user, roles=roles)
