"""The marker an entry point that only stands in wears, so a real one wins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from .authentication_entry_point_interface import AuthenticationEntryPointInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError

__all__ = ["FallbackAuthenticationEntryPointInterface"]


class FallbackAuthenticationEntryPointInterface(AuthenticationEntryPointInterface):
    """An entry point that only stands in for a firewall declaring no other one.

    An authenticator wears this marker when it can answer an unauthenticated
    request with a meaningful challenge, but has no authentication to start —
    a bearer challenge names the scheme, it does not begin a login — and must
    therefore never win over an entry point that does, a login form say. A
    firewall that holds one of each keeps picking the other, so an
    authenticator gaining a fallback entry point never makes an existing
    firewall ambiguous.

    Having no authentication to start, it also gets no target path saved for
    it: answering an unauthenticated request through it never starts a
    session, so there is nothing for the caller to come back to.

    The base contract is restated here because a marker a runtime check reads
    — the exception listener asking which entry point it holds — cannot be a
    ``Protocol`` the check would answer ``True`` for regardless. An entry point
    that stands in inherits this and answers ``start`` its own way.
    """

    __slots__: tuple[str, ...] = ()

    @override
    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        """Return the response that asks ``request`` to authenticate.

        Args:
            request: The request that reached a protected resource.
            error: The authentication error that led here, when one did, so the
                challenge can name why — a bad token, insufficient scope.
        """
        raise NotImplementedError
