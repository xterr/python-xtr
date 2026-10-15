"""The token of a user who temporarily acts as another one."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .username_password_token import UsernamePasswordToken

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.user.user_interface import UserInterface

    from .token_interface import TokenInterface

__all__ = ["SwitchUserToken"]


@final
class SwitchUserToken(UsernamePasswordToken):
    """A user impersonating another one, with the way back kept.

    Switching user re-authenticates as the target while keeping the token
    the switch started from, so the impersonator can return to themselves.
    For everything downstream the token is a full username/password token
    for the target user — the switch itself is the proof — plus the
    original token and, when the switch came from a request, where that
    request was.

    Attributes:
        originated_from_uri: The URI the switch was made at, when it was
            made at one.
    """

    __slots__: tuple[str, ...] = ("_original_token", "_originated_from_uri")

    _original_token: TokenInterface
    _originated_from_uri: str | None

    def __init__(
        self,
        user: UserInterface,
        firewall_name: str,
        roles: Sequence[str],
        original_token: TokenInterface,
        originated_from_uri: str | None = None,
    ) -> None:
        """Record the target user, the original token, and where the switch happened.

        Args:
            user: The user being switched to.
            firewall_name: The firewall the switch happened in.
            roles: The roles fixed on the target user's token.
            original_token: The token of the user who switched.
            originated_from_uri: The URI the switch was made at, when it was.

        Raises:
            InvalidArgumentError: When ``firewall_name`` is empty.
        """
        super().__init__(user, firewall_name, roles)
        self._original_token = original_token
        self._originated_from_uri = originated_from_uri

    def get_original_token(self) -> TokenInterface:
        """Return the token of the user who switched."""
        return self._original_token

    def get_originated_from_uri(self) -> str | None:
        """Return the URI the switch was made at, or ``None`` when it was not."""
        return self._originated_from_uri
