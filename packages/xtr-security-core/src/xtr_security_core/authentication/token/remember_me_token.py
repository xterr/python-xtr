"""The token a remembered login settles on."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_core.exception import InvalidArgumentError

from .abstract_token import AbstractToken

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["RememberMeToken"]


@final
class RememberMeToken(AbstractToken):
    """A user remembered from an earlier login, not freshly proven.

    A remember-me cookie re-establishes who is calling without a password.
    The token carries the user and the firewall the cookie was issued for,
    with the user's own roles — a remembered login has no moment of its own
    to fix roles at, so it reads them from the user when the cookie is
    presented. It is an authenticated token, but a weaker one: a trust
    resolver tells it apart from a fully proven login.

    Attributes:
        firewall_name: The firewall the remember-me cookie was issued for.
    """

    __slots__: tuple[str, ...] = ("_firewall_name",)

    _firewall_name: str

    def __init__(self, user: UserInterface, firewall_name: str) -> None:
        """Record the remembered user and the firewall their cookie was issued for.

        Raises:
            InvalidArgumentError: When ``firewall_name`` is empty.
        """
        super().__init__(user.get_roles())
        if firewall_name == "":
            raise InvalidArgumentError('The "firewall_name" must not be empty.')
        self._firewall_name = firewall_name
        self.set_user(user)

    def get_firewall_name(self) -> str:
        """Return the firewall the remember-me cookie was issued for."""
        return self._firewall_name
