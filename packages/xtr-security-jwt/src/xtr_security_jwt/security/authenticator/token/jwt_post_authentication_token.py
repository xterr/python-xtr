"""The security token a self-issued-token authentication settles on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["JwtPostAuthenticationToken"]


@final
class JwtPostAuthenticationToken(PostAuthenticationToken):
    """A post-authentication token carrying the raw token it was proved by.

    A token whose roles were fixed the moment it authenticated, that also keeps
    the compact token alongside — so the token manager can read the credentials
    back out of a stored token, to decode its claims or to block it. It carries
    the firewall it belongs to, like the family's own post-authentication token.

    It can sit in a stateful firewall, so a session keeps it too: the compact
    token beside the firewall, the roles and the attributes, as the plain JSON
    of the session store.
    """

    __slots__ = ("_raw_token",)

    def __init__(
        self,
        user: UserInterface,
        firewall_name: str,
        roles: Sequence[str],
        raw_token: str,
    ) -> None:
        """Record the user, firewall, roles and the ``raw_token`` proved by."""
        super().__init__(user, firewall_name, roles)
        self._raw_token = raw_token

    def get_credentials(self) -> str:
        """Return the raw compact token this authentication was proved by."""
        return self._raw_token

    @override
    def to_session(
        self,
        encode_token: Callable[[TokenInterface], dict[str, object]],
    ) -> dict[str, object]:
        """Return the post-authentication token's state and the compact token, for a session."""
        return {**super().to_session(encode_token), "raw_token": self._raw_token}

    @classmethod
    @override
    def from_session(
        cls,
        state: Mapping[str, object],
        user: UserInterface | None,
        decode_token: Callable[[object], TokenInterface | None],
    ) -> Self:
        """Rebuild the token a session kept, the compact token included.

        Raises:
            InvalidArgumentError: When a field of ``state`` is missing or of
                the wrong type, or the compact token or the firewall is empty.
        """
        raw_token = state.get("raw_token")
        if not isinstance(raw_token, str) or raw_token == "":
            raise InvalidArgumentError(
                'The session state\'s "raw_token" must be a non-empty string.',
            )
        token = super().from_session(state, user, decode_token)
        token._raw_token = raw_token  # noqa: SLF001 -- the token this very class rebuilds
        return token
