"""The listener that turns a security error into a response on the lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from starlette.responses import JSONResponse
from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_http_kernel import ExceptionEvent
from xtr_security_core.authentication.authentication_trust_resolver_interface import (  # noqa: TC002
    AuthenticationTrustResolverInterface,
)
from xtr_security_core.exception import (
    AccessDeniedError,
    AuthenticationError,
    InsufficientAuthenticationError,
)

from xtr_security_http._challenge import no_store_headers
from xtr_security_http._state import FIREWALL_CONTEXT_KEY, TOKEN_KEY, CarriedResponse
from xtr_security_http.authorization.oauth2_scope_voter import parse_oauth2_scope

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_event_dispatcher import SubscribedEvents
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.firewall_context_interface import FirewallContextInterface

__all__ = ["ExceptionListener"]


@final
class ExceptionListener(EventSubscriberInterface):
    """Turns a security error raised while handling a request into a response.

    Sits on the lifecycle's exception event, alone deciding ``401`` versus
    ``403``:

    - a carried handler response is sent as it is;
    - an :class:`~xtr_security_core.exception.AuthenticationError` becomes the
      firewall's entry-point challenge, or a bare ``401`` bearer challenge when
      the firewall has no entry point;
    - an :class:`~xtr_security_core.exception.AccessDeniedError` from a caller who
      is not fully authenticated becomes the entry-point challenge for
      insufficient authentication; from a fully authenticated caller it becomes
      a scope challenge when the denied attribute is a scope, the firewall's
      access-denied handler when it has one, or a plain ``403`` otherwise.

    Any other exception is left untouched, to whatever else handles it.

    The firewall the request ran under, and the token it authenticated, are read
    from ``request.state`` — stashed there by the firewall — so this singleton
    listener answers a request without reaching into the request scope. The
    trust resolver is a singleton it is built with.
    """

    __slots__ = ("_trust_resolver",)

    def __init__(self, trust_resolver: AuthenticationTrustResolverInterface) -> None:
        """Build the listener over the application's trust resolver."""
        self._trust_resolver = trust_resolver

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to the lifecycle's exception event."""
        return {ExceptionEvent: "on_exception"}

    async def on_exception(self, event: ExceptionEvent) -> None:
        """Answer the request when the exception is one this listener owns."""
        error = event.exception
        if isinstance(error, CarriedResponse):
            event.set_response(error.response)
            return
        if not isinstance(error, (AuthenticationError, AccessDeniedError)):
            return
        context = _context_of(event.request)
        if isinstance(error, AuthenticationError):
            event.set_response(await self._on_authentication_error(context, event.request, error))
            return
        event.set_response(await self._on_access_denied(context, event.request, error))

    async def _on_authentication_error(
        self,
        context: FirewallContextInterface | None,
        request: Request,
        error: AuthenticationError,
    ) -> Response:
        """Answer an authentication error with the entry-point challenge, or a bare 401."""
        if context is not None and context.entry_point is not None:
            return await context.entry_point.start(request, error)
        return _bare_challenge()

    async def _on_access_denied(
        self,
        context: FirewallContextInterface | None,
        request: Request,
        error: AccessDeniedError,
    ) -> Response:
        """Answer a denial: a challenge when not fully authenticated, else a refusal."""
        if not self._is_full_fledged(request):
            if context is not None and context.entry_point is not None:
                return await context.entry_point.start(request, InsufficientAuthenticationError())
            return _bare_challenge()
        if (
            _is_scope_denial(error)
            and context is not None
            and context.scope_denied_handler is not None
        ):
            answered = await context.scope_denied_handler.handle(request, error)
            if answered is not None:
                return answered
        if context is not None and context.access_denied_handler is not None:
            answered = await context.access_denied_handler.handle(request, error)
            if answered is not None:
                return answered
        return JSONResponse(
            {"error": "access_denied"},
            status_code=403,
            headers=no_store_headers(),
        )

    def _is_full_fledged(self, request: Request) -> bool:
        """Tell whether the request's token is fully authenticated."""
        token = _token_of(request)
        return self._trust_resolver.is_full_fledged(token)


def _context_of(request: Request) -> FirewallContextInterface | None:
    """Return the firewall context the firewall stashed for ``request``, if any."""
    context = getattr(request.state, FIREWALL_CONTEXT_KEY, None)
    return cast("FirewallContextInterface | None", context)


def _token_of(request: Request) -> TokenInterface | None:
    """Return the token the firewall stashed for ``request``, if any."""
    return cast("TokenInterface | None", getattr(request.state, TOKEN_KEY, None))


def _bare_challenge() -> Response:
    """Return a plain ``401`` carrying a bare bearer challenge."""
    return JSONResponse(
        {"error": "unauthorized"},
        status_code=401,
        headers=no_store_headers(**{"WWW-Authenticate": "Bearer"}),
    )


def _is_scope_denial(error: AccessDeniedError) -> bool:
    """Tell whether the denied attribute is an OAuth2 scope request."""
    return any(parse_oauth2_scope(attribute) is not None for attribute in error.attributes)
