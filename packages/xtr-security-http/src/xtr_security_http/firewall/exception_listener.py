"""The listener that turns a security error into a response on the lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_http_kernel import ExceptionEvent
from xtr_http_kernel.bridge import Response as FrameworkResponse
from xtr_http_kernel.bridge import StarletteHttpFactoryInterface
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
)
from xtr_security_core.authentication.authentication_trust_resolver_interface import (  # noqa: TC002
    AuthenticationTrustResolverInterface,
)
from xtr_security_core.exception import (
    AccessDeniedError,
    AuthenticationError,
    InsufficientAuthenticationError,
)

from xtr_security_http._challenge import json_challenge
from xtr_security_http._security_state import CarriedResponse, security_state_of
from xtr_security_http.authorization.oauth2_scope_voter import parse_oauth2_scope

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_http._security_state import SecurityState

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

    The firewall the request ran under and the token it authenticated are read
    from the request's security state — parked on the state bag the event
    carries, the same one the framework's request wraps — so this singleton
    listener answers a request without reaching into the request scope. The
    trust resolver, the response factory it builds its bare answers with and
    the bridge that turns a handler's pure message response into one the
    lifecycle can send are singletons it is built with.

    A response that already is what the framework sends — the kernel's own
    dual response, a message and a framework response at once — is set on the
    event as it is; a pure message is converted through the bridge first,
    which is the kernel's rule for messages from elsewhere.
    """

    __slots__ = ("_bridge", "_responses", "_trust_resolver")

    def __init__(
        self,
        trust_resolver: AuthenticationTrustResolverInterface,
        responses: ResponseFactoryInterface,
        bridge: StarletteHttpFactoryInterface,
    ) -> None:
        """Build the listener over the trust resolver, the response factory and the bridge.

        Args:
            trust_resolver: Weighs the token the firewall authenticated.
            responses: Builds the bare ``401``/``403`` answers, so the listener
                names no response class.
            bridge: Turns a handler's pure message response into one the
                lifecycle's event accepts.
        """
        self._trust_resolver = trust_resolver
        self._responses = responses
        self._bridge = bridge

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to the lifecycle's exception event."""
        return {ExceptionEvent: "on_exception"}

    async def on_exception(self, event: ExceptionEvent) -> None:
        """Answer the request when the exception is one this listener owns."""
        error = event.exception
        if isinstance(error, CarriedResponse):
            await self._answer(event, error.response)
            return
        if not isinstance(error, (AuthenticationError, AccessDeniedError)):
            return
        state = security_state_of(event.state)
        if isinstance(error, AuthenticationError):
            answered = await self._on_authentication_error(state, event.request, error)
        else:
            answered = await self._on_access_denied(state, event.request, error)
        await self._answer(event, answered)

    async def _on_authentication_error(
        self,
        state: SecurityState,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Answer an authentication error with the entry-point challenge, or a bare 401."""
        context = state.firewall_context
        if context is not None and context.entry_point is not None:
            return await context.entry_point.start(request, error)
        return await self._bare_challenge()

    async def _on_access_denied(
        self,
        state: SecurityState,
        request: ServerRequestInterface,
        error: AccessDeniedError,
    ) -> ResponseInterface:
        """Answer a denial: a challenge when not fully authenticated, else a refusal."""
        context = state.firewall_context
        if not self._trust_resolver.is_full_fledged(state.token):
            if context is not None and context.entry_point is not None:
                return await context.entry_point.start(
                    request,
                    InsufficientAuthenticationError(),
                )
            return await self._bare_challenge()
        if (
            context is not None
            and _is_scope_denial(error)
            and context.scope_denied_handler is not None
        ):
            answered = await context.scope_denied_handler.handle(request, error)
            if answered is not None:
                return answered
        if context is not None and context.access_denied_handler is not None:
            answered = await context.access_denied_handler.handle(request, error)
            if answered is not None:
                return answered
        return await self._forbidden()

    async def _bare_challenge(self) -> ResponseInterface:
        """Return a plain ``401`` carrying a bare bearer challenge."""
        return await json_challenge(
            self._responses,
            401,
            {"error": "unauthorized"},
            {"WWW-Authenticate": "Bearer"},
        )

    async def _forbidden(self) -> ResponseInterface:
        """Return a plain, uncached ``403`` refusing the request."""
        return await json_challenge(
            self._responses,
            403,
            {"error": "access_denied"},
            {},
        )

    async def _answer(self, event: ExceptionEvent, response: ResponseInterface) -> None:
        """Set ``response`` on ``event`` as what the lifecycle can send.

        The kernel's own response is both a message and what the framework
        sends, so it is set as it is; a pure message — a handler built through
        another factory, a test's own — is converted through the bridge, the
        kernel's rule for messages from elsewhere.
        """
        if isinstance(response, FrameworkResponse):
            event.set_response(response)
            return
        event.set_response(await self._bridge.create_response(response))


def _is_scope_denial(error: AccessDeniedError) -> bool:
    """Tell whether the denied attribute is an OAuth2 scope request."""
    return any(parse_oauth2_scope(attribute) is not None for attribute in error.attributes)
