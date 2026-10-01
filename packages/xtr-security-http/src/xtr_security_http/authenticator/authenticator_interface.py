"""What an authenticator — one way of proving who is calling — answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError

    from .passport.passport import Passport

__all__ = ["AuthenticatorInterface"]


@runtime_checkable
class AuthenticatorInterface(Protocol):
    """One way of authenticating a request, from a bearer token to a form post.

    A firewall runs its authenticators in order. Each is asked whether it
    :meth:`supports` the request; the first that does authenticates it,
    producing a passport the manager checks and turns into a token. The two
    ``on_authentication_*`` hooks let an authenticator answer the request
    itself — a redirect on success, a challenge on failure — rather than
    letting the request go on to its endpoint.
    """

    def supports(self, request: Request) -> bool | None:
        """Tell whether this authenticator handles ``request``.

        ``True`` authenticates it and stops the others; ``False`` skips it;
        ``None`` authenticates it but lets a later authenticator try too if
        this one produces no token — a lazy authenticator with no credential
        present in the request.
        """
        ...

    async def authenticate(self, request: Request) -> Passport:
        """Read ``request`` into a passport, before any badge is resolved.

        Raises:
            AuthenticationError: When the request cannot even be read into a
                passport — a malformed token, a missing field.
        """
        ...

    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Turn a resolved ``passport`` into the token authentication settles on."""
        ...

    async def on_authentication_success(
        self,
        request: Request,
        token: TokenInterface,
        firewall_name: str,
    ) -> Response | None:
        """React to a successful authentication, optionally answering the request."""
        ...

    async def on_authentication_failure(
        self,
        request: Request,
        error: AuthenticationError,
    ) -> Response | None:
        """React to a failed authentication, optionally answering the request."""
        ...
