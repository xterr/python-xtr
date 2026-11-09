"""The token a remembered login settles on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from typing_extensions import override

from xtr_security_core._session_state import string_field
from xtr_security_core.exception import InvalidArgumentError

from .abstract_token import AbstractToken

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_security_core.user.user_interface import UserInterface

    from .token_interface import TokenInterface

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

    Rebuilt from a session, it restores the roles it was created with: they
    were read from the user when the cookie was presented, and a role the
    user lost since is what the reload of the user weighs, not what the
    rebuild hides.

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

    @override
    def to_session(
        self,
        encode_token: Callable[[TokenInterface], dict[str, object]],
    ) -> dict[str, object]:
        """Return the roles, the attributes and the firewall, for a session to keep."""
        return {**super().to_session(encode_token), "firewall": self._firewall_name}

    @classmethod
    @override
    def from_session(
        cls,
        state: Mapping[str, object],
        user: UserInterface | None,
        decode_token: Callable[[object], TokenInterface | None],
    ) -> Self:
        """Rebuild the token a session kept, with the roles it kept, not the user's.

        Raises:
            InvalidArgumentError: When a field of ``state`` is missing or of
                the wrong type, or the firewall is empty.
        """
        token = super().from_session(state, user, decode_token)
        token._firewall_name = string_field(state, "firewall")  # noqa: SLF001 -- the token this very class rebuilds
        return token
