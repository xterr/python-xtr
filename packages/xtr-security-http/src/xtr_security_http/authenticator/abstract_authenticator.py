"""A starting point for an authenticator: the token, and no-op hooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken

from .authenticator_interface import AuthenticatorInterface

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError

    from .passport.passport import Passport

__all__ = ["AbstractAuthenticator"]


class AbstractAuthenticator(  # pyright: ignore[reportImplicitAbstractClass]  -- subclasses implement supports/authenticate
    AuthenticatorInterface,
):
    """The parts of an authenticator every kind shares.

    Turns a resolved passport into a
    :class:`~xtr_security_http.authenticator.token.post_authentication_token.PostAuthenticationToken`
    carrying the user and its roles, and answers both ``on_authentication_*``
    hooks with ``None`` — letting the request go on. A concrete authenticator
    overrides :meth:`supports` and :meth:`authenticate`, and either hook when
    it wants to answer the request itself.
    """

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build a post-authentication token for the passport's user and roles.

        The user is read from the passport's user badge, which the passport
        check already loaded, so this call does no I/O.
        """
        user = passport.get_user_badge().get_loaded_user()
        return PostAuthenticationToken(user, firewall_name, user.get_roles())

    @override
    async def on_authentication_success(
        self,
        request: Request,
        token: TokenInterface,
        firewall_name: str,
    ) -> Response | None:
        """Answer nothing: the request goes on to its endpoint."""
        del request, token, firewall_name
        return None

    @override
    async def on_authentication_failure(
        self,
        request: Request,
        error: AuthenticationError,
    ) -> Response | None:
        """Answer nothing: the failure is turned into a challenge elsewhere."""
        del request, error
        return None
