"""The security token a self-issued-token authentication settles on."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["JwtPostAuthenticationToken"]


@final
class JwtPostAuthenticationToken(PostAuthenticationToken):
    """A post-authentication token carrying the raw token it was proved by.

    A token whose roles were fixed the moment it authenticated, that also keeps
    the compact token alongside — so the token manager can read the credentials
    back out of a stored token, to decode its claims or to block it. It carries
    the firewall it belongs to, like the family's own post-authentication token.
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
