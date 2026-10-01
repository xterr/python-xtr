"""The token authentication settles on once a user is established."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core.authentication.token.abstract_token import AbstractToken

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["PostAuthenticationToken"]


class PostAuthenticationToken(AbstractToken):
    """A user, the firewall that authenticated them, and the roles decided.

    The ordinary outcome of a successful authentication. It lives in the core,
    not only at the HTTP edge, because a worker or a command authenticates the
    same way — it sets one of these on the token storage without a request ever
    being involved.

    Attributes:
        firewall_name: The firewall (or unit of work) that authenticated.
    """

    _firewall_name: str

    def __init__(
        self,
        user: UserInterface,
        firewall_name: str,
        roles: Sequence[str],
    ) -> None:
        """Record the user, the firewall that authenticated them, and their roles."""
        super().__init__(user=user, roles=roles)
        self._firewall_name = firewall_name

    def get_firewall_name(self) -> str:
        """Return the firewall (or unit of work) that authenticated the user."""
        return self._firewall_name
