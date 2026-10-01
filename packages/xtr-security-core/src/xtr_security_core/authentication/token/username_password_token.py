"""A token naming a user, the firewall that authenticated them, and their roles."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .abstract_token import AbstractToken

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["UsernamePasswordToken"]


@final
class UsernamePasswordToken(AbstractToken):
    """A user proven by a password, the firewall that did it, and the roles.

    The token an authentication settles on when a user answered with a
    password. It carries the user, the firewall (or unit of work) that
    authenticated them, and the roles fixed at that moment — decoupled from the
    live user's roles, as every token in this library is.

    Attributes:
        firewall_name: The firewall (or unit of work) that authenticated.
    """

    def __init__(
        self,
        user: UserInterface,
        firewall_name: str,
        roles: Sequence[str] = (),
    ) -> None:
        """Record the user, the firewall that authenticated them, and their roles."""
        super().__init__(user=user, roles=roles)
        self._firewall_name = firewall_name

    def get_firewall_name(self) -> str:
        """Return the firewall (or unit of work) that authenticated the user."""
        return self._firewall_name
