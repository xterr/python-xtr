"""The token of a user who temporarily acts as another one."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from typing_extensions import override

from xtr_security_core._session_state import optional_string_field
from xtr_security_core.exception import InvalidArgumentError

from .username_password_token import UsernamePasswordToken

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

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

    A session keeps the original token nested in this one's state, the same
    way it keeps any token, so the way back survives the request too.

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

    @override
    def to_session(
        self,
        encode_token: Callable[[TokenInterface], dict[str, object]],
    ) -> dict[str, object]:
        """Return the switched token's state, the original kept nested as any token is."""
        return {
            **super().to_session(encode_token),
            "original": encode_token(self._original_token),
            "originated_from_uri": self._originated_from_uri,
        }

    @classmethod
    @override
    def from_session(
        cls,
        state: Mapping[str, object],
        user: UserInterface | None,
        decode_token: Callable[[object], TokenInterface | None],
    ) -> Self:
        """Rebuild the switch a session kept, the original rebuilt as any token is.

        Raises:
            InvalidArgumentError: When a field of ``state`` is missing or of
                the wrong type, or the original is no token the session can
                rebuild.
        """
        token = super().from_session(state, user, decode_token)
        original = decode_token(state.get("original"))
        if original is None:
            raise InvalidArgumentError(
                'The session state\'s "original" must be a token the session can rebuild.',
            )
        token._original_token = original  # noqa: SLF001 -- the token this very class rebuilds
        token._originated_from_uri = optional_string_field(state, "originated_from_uri")  # noqa: SLF001 -- the token this very class rebuilds
        return token
