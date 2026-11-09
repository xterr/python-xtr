"""A token naming a user, the firewall that authenticated them, and their roles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override

from xtr_security_core._session_state import string_field
from xtr_security_core.exception import InvalidArgumentError

from .abstract_token import AbstractToken

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from xtr_security_core.user.user_interface import UserInterface

    from .token_interface import TokenInterface

__all__ = ["UsernamePasswordToken"]


class UsernamePasswordToken(AbstractToken):
    """A user proven by a password, the firewall that did it, and the roles.

    The token an authentication settles on when a user answered with a
    password. It carries the user, the firewall (or unit of work) that
    authenticated them, and the roles fixed at that moment — decoupled from
    the live user's roles, as every token in this library is. Open for
    subclassing, because a token can be a password token with something
    added — the switch-user token is one.

    Attributes:
        firewall_name: The firewall (or unit of work) that authenticated.
    """

    __slots__: tuple[str, ...] = ("_firewall_name",)

    _firewall_name: str

    def __init__(
        self,
        user: UserInterface,
        firewall_name: str,
        roles: Sequence[str] = (),
    ) -> None:
        """Record the user, the firewall that authenticated them, and their roles.

        Raises:
            InvalidArgumentError: When ``firewall_name`` is empty.
        """
        super().__init__(roles)
        if firewall_name == "":
            raise InvalidArgumentError('The "firewall_name" must not be empty.')
        self._firewall_name = firewall_name
        self.set_user(user)

    def get_firewall_name(self) -> str:
        """Return the firewall (or unit of work) that authenticated the user."""
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
        """Rebuild the token a session kept, its firewall included.

        Raises:
            InvalidArgumentError: When a field of ``state`` is missing or of
                the wrong type, or the firewall is empty.
        """
        token = super().from_session(state, user, decode_token)
        token._firewall_name = string_field(state, "firewall")  # noqa: SLF001 -- the token this very class rebuilds
        return token
