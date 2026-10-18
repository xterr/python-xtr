"""A request driven through the kernel events, firewalled by the subscriber.

The acceptance shape of the chain: the real manager and access steps a
secured firewall runs, composed over a real map and driven through a real
dispatcher — the state the chain's caller parks, the order the chain runs
in, the listener that answers a failure, and the finish that puts it away.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_foundation import PathRequestMatcher
from xtr_http_kernel import ExceptionEvent, FinishRequestEvent, RequestEvent
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_http_message import Response as PureResponse
from xtr_security_core.authentication.authentication_trust_resolver import (
    AuthenticationTrustResolver,
)
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import AccessDecisionManager, RoleVoter
from xtr_security_core.exception import AccessDeniedError
from xtr_security_core.user import InMemoryUser

from tests.support.contexts import FakeFirewallContext
from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.access_map import AccessMap
from xtr_security_http.authenticator.token import PostAuthenticationToken
from xtr_security_http.firewall._subscriber import FirewallSubscriber
from xtr_security_http.firewall.access_listener import AccessListener
from xtr_security_http.firewall.authenticator_manager_listener import (
    AuthenticatorManagerListener,
)
from xtr_security_http.firewall.exception_listener import ExceptionListener
from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http._security_state import SecurityState

pytestmark = pytest.mark.anyio


@final
class _Manager:
    """Authenticates the way the real manager would: storing a token, or answering."""

    def __init__(
        self,
        token_storage: TokenStorage,
        *,
        token: TokenInterface | None = None,
        response: ResponseInterface | None = None,
    ) -> None:
        """Store ``token`` or answer ``response`` when this manager authenticates."""
        self._token_storage = token_storage
        self._token = token
        self._response = response

    def supports(self, request: ServerRequestInterface, state: SecurityState) -> bool | None:
        """Join the chain lazily: nothing in the head committed an authenticator."""
        del request, state
        return None

    async def authenticate_request(
        self,
        request: ServerRequestInterface,
        state: SecurityState,
    ) -> ResponseInterface | None:
        """Store the token this manager was built with, or answer with its response."""
        del request, state
        if self._response is not None:
            return self._response
        if self._token is not None:
            self._token_storage.set_token(self._token)
        return None


def _secured_firewall(
    manager: _Manager,
    token_storage: TokenStorage,
    *rules: tuple[str, str],
) -> FirewallMap:
    """Return a map of one secured firewall over the real chain steps."""
    access_map = AccessMap()
    for path, attribute in rules:
        access_map.add(PathRequestMatcher(path), attribute)
    manager_step = AuthenticatorManagerListener(manager, StarletteHttpFactory())
    access_step = AccessListener(
        token_storage,
        AccessDecisionManager([RoleVoter()]),
        access_map,
    )
    # The order the bundle's sorting pass leaves a chain in: the manager
    # step at 0 ahead of the access step at -255.
    chain = sorted(
        (manager_step, access_step),
        key=lambda step: -step.get_priority(),
    )
    return FirewallMap(
        [
            (
                PathRequestMatcher("^/api"),
                FakeFirewallContext(
                    name="api",
                    authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                    access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                    scheme=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                    listeners=tuple(chain),
                    exception_listener=ExceptionListener(
                        AuthenticationTrustResolver(),
                        ResponseFactory(),
                        StarletteHttpFactory(),
                    ),
                ),
            ),
        ],
    )


def _dispatcher(firewall_map: FirewallMap) -> EventDispatcher:
    """Return a dispatcher with the firewall subscribed to the lifecycle."""
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(FirewallSubscriber(firewall_map))
    return dispatcher


async def test_the_chain_authenticates_before_it_decides() -> None:
    """The manager step runs first, so the access step decides an authenticated token.

    Were the order the other way round, the access step would decide the
    empty storage's null token against ``ROLE_USER`` and refuse the request.
    """
    token_storage = TokenStorage()
    manager = _Manager(
        token_storage,
        token=PostAuthenticationToken(InMemoryUser("alice"), "api", ["ROLE_USER"]),
    )
    dispatcher = _dispatcher(_secured_firewall(manager, token_storage, (r"^/api", "ROLE_USER")))
    bag: dict[str, object] = {}

    _ = await dispatcher.dispatch(RequestEvent(make_message(path="/api/books"), bag))

    stored = token_storage.get_token()
    assert stored is not None
    user = stored.get_user()
    assert user is not None
    assert user.get_user_identifier() == "alice"


async def test_the_stored_listener_answers_a_denied_request_and_finish_clears_it() -> None:
    token_storage = TokenStorage()
    dispatcher = _dispatcher(
        _secured_firewall(_Manager(token_storage), token_storage, (r"^/api", "ROLE_ADMIN")),
    )
    bag: dict[str, object] = {}
    request = make_message(path="/api/books")

    with pytest.raises(AccessDeniedError) as raised:
        _ = await dispatcher.dispatch(RequestEvent(request, bag))

    failure = ExceptionEvent(request, bag, raised.value)
    _ = await dispatcher.dispatch(failure)

    assert failure.response is not None
    assert failure.response.status_code == 401
    assert failure.response.headers["WWW-Authenticate"] == "Bearer"

    _ = await dispatcher.dispatch(FinishRequestEvent(request, bag))

    assert SecurityRequestAttributes.EXCEPTION_LISTENER not in security_state_of(bag).attributes


async def test_a_response_from_the_manager_step_short_circuits_the_chain() -> None:
    token_storage = TokenStorage()
    manager = _Manager(
        token_storage,
        response=PureResponse(302, None, None, "1.1").with_header("location", "/login"),
    )
    dispatcher = _dispatcher(_secured_firewall(manager, token_storage, (r"^/api", "ROLE_USER")))
    bag: dict[str, object] = {}
    event = RequestEvent(make_message(path="/api/books"), bag)

    _ = await dispatcher.dispatch(event)

    assert event.response is not None
    assert event.response.status_code == 302
    assert event.response.headers["location"] == "/login"
    # The access step never ran: nothing it would have parked is on the
    # carrier, and no token was stored.
    assert (
        SecurityRequestAttributes.ACCESS_CONTROL_ATTRIBUTES not in security_state_of(bag).attributes
    )
    assert token_storage.get_token() is None
