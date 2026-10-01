"""What turns a bearer access token into the badge naming its user."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge

__all__ = ["AccessTokenHandlerInterface"]


@runtime_checkable
class AccessTokenHandlerInterface(Protocol):
    """Validates an access token and reports who it was issued for.

    A handler is the whole of what makes a bearer token trustworthy: it
    verifies the token — a JWT's signature and claims, an introspection
    call — and returns a
    :class:`~xtr_security_http.authenticator.passport.badge.user_badge.UserBadge`
    naming the user, its attributes carrying the token's ``scope``,
    ``client_id``, ``jti`` and remaining claims. This is the seam an OAuth2
    resource server plugs its own token validation into.
    """

    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Return the user badge ``access_token`` proves.

        Raises:
            AuthenticationError: When the token cannot be trusted — most often
                an :class:`InvalidAccessTokenError` for a malformed, expired or
                wrongly signed token.
        """
        ...
