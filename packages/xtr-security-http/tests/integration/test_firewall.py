"""A request driven through the kernel events, firewalled by the subscriber.

The acceptance shape of the chain: the real manager and access steps a
secured firewall runs, composed over a real map and driven through a real
dispatcher — the state the chain's caller parks, the order the chain runs
in, the listener that answers a failure, and the finish that puts it away.
The seam the bundle's registration leaves: the firewall subscribed beside
the global exception listener, a firewalled failure answered exactly once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_foundation import MemorySessionStorage, PathRequestMatcher, Session
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
from xtr_security_http._parked_session import parked_session_of
from xtr_security_http._security_state import security_state_of
from xtr_security_http.access_map import AccessMap
from xtr_security_http.authenticator.token import PostAuthenticationToken
from xtr_security_http.firewall.access_listener import AccessListener
from xtr_security_http.firewall.authenticator_manager_listener import (
    AuthenticatorManagerListener,
)
from xtr_security_http.firewall.exception_listener import ExceptionListener
from xtr_security_http.firewall.firewall import Firewall
from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http._security_state import SecurityState

pytestmark = pytest.mark.anyio


def _exception_listener() -> ExceptionListener:
    """Return the listener a secured firewall stores for its requests."""
    return ExceptionListener(
        TokenStorage(),
        AuthenticationTrustResolver(),
        ResponseFactory(),
        StarletteHttpFactory(),
        "api",
    )


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
                    listeners=tuple(chain),
                    exception_listener=ExceptionListener(
                        TokenStorage(),
                        AuthenticationTrustResolver(),
                        ResponseFactory(),
                        StarletteHttpFactory(),
                        "api",
                    ),
                ),
            ),
        ],
    )


def _dispatcher(
    firewall_map: FirewallMap, *, with_the_global_listener: bool = False
) -> EventDispatcher:
    """Return a dispatcher with the firewall subscribed to the lifecycle.

    ``with_the_global_listener`` registers the global exception listener the
    way the bundle does — the same listener the firewall stores for its
    requests — so the seam between the firewall's exception phase and the
    global subscription can be driven.
    """
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(Firewall(firewall_map))
    if with_the_global_listener:
        dispatcher.add_listener(
            ExceptionEvent,
            _exception_listener().on_exception,
        )
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


async def test_a_denied_request_is_answered_on_the_request_event_and_finish_clears_it() -> None:
    token_storage = TokenStorage()
    dispatcher = _dispatcher(
        _secured_firewall(_Manager(token_storage), token_storage, (r"^/api", "ROLE_ADMIN")),
    )
    bag: dict[str, object] = {}
    request = make_message(path="/api/books")
    event = RequestEvent(request, bag)

    _ = await dispatcher.dispatch(event)

    # The denial the access step raised at the request was announced on the
    # exception event and answered by the stored listener, and the answer
    # was set on the request's own event: the request is answered, not failed.
    assert event.response is not None
    assert event.response.status_code == 401
    assert event.response.headers["WWW-Authenticate"] == "Bearer"

    _ = await dispatcher.dispatch(FinishRequestEvent(request, bag))

    assert SecurityRequestAttributes.EXCEPTION_LISTENER not in security_state_of(bag).attributes


async def test_a_firewalled_failure_is_answered_exactly_once() -> None:
    """The stored listener answers; the global subscription does not answer again.

    The bundle registers the global exception listener beside the firewall,
    and the firewall stores that same listener for its requests. A firewalled
    failure reaches it once — through the firewall's exception phase, whose
    answer stops the event — and the global subscription never runs.
    """
    answered: list[ExceptionEvent] = []

    async def counting_global(event: ExceptionEvent) -> None:
        answered.append(event)
        await _exception_listener().on_exception(event)

    token_storage = TokenStorage()
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(
        Firewall(
            _secured_firewall(_Manager(token_storage), token_storage, (r"^/api", "ROLE_ADMIN"))
        )
    )
    dispatcher.add_listener(ExceptionEvent, counting_global)
    bag: dict[str, object] = {}

    event = RequestEvent(make_message(path="/api/books"), bag)
    _ = await dispatcher.dispatch(event)

    assert event.response is not None
    assert event.response.status_code == 401
    # The stored listener answered through the firewall's exception phase;
    # the global subscription was skipped by the answer's stop.
    assert answered == []


async def test_an_unmatched_requests_failure_is_answered_by_the_global_listener() -> None:
    """A request no firewall claims stores no listener; the global one answers."""
    token_storage = TokenStorage()
    dispatcher = _dispatcher(
        _secured_firewall(_Manager(token_storage), token_storage, (r"^/api", "ROLE_USER")),
        with_the_global_listener=True,
    )
    bag: dict[str, object] = {}

    # A request outside the firewall's matcher: nothing stored, so the
    # firewall's exception phase leaves the failure to the global listener.
    failure = ExceptionEvent(make_message(path="/public"), bag, AccessDeniedError("denied"))
    _ = await dispatcher.dispatch(failure)

    assert failure.response is not None
    assert failure.response.status_code == 401
    assert failure.response.headers["WWW-Authenticate"] == "Bearer"


async def test_a_manager_hook_reads_the_parked_session_of_the_live_chain() -> None:
    """The request the manager authenticates carries the event's bag, not a bagless copy.

    The kernel event parks its bag only on the request the chain's supports
    asks about; the manager step must hand the authenticate pass a request
    that carries the same bag, or a hook reading the session off the request
    finds nothing in the live chain.
    """
    token_storage = TokenStorage()
    seen: list[object] = []

    @final
    class _ReadingManager:
        """Reads the session off the request the manager is handed, then answers nothing."""

        def supports(self, request: ServerRequestInterface, state: SecurityState) -> bool | None:
            del request, state
            return None

        async def authenticate_request(
            self,
            request: ServerRequestInterface,
            state: SecurityState,
        ) -> ResponseInterface | None:
            del state
            seen.append(parked_session_of(request))
            return None

    session = Session(MemorySessionStorage())
    bag: dict[str, object] = {}
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    manager_step = AuthenticatorManagerListener(
        _ReadingManager(),
        StarletteHttpFactory(),
    )
    access_step = AccessListener(
        token_storage,
        AccessDecisionManager([RoleVoter()]),
        AccessMap(),
    )
    dispatcher = _dispatcher(
        FirewallMap(
            [
                (
                    PathRequestMatcher("^/api"),
                    FakeFirewallContext(
                        name="api",
                        authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                        access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                        listeners=(manager_step, access_step),
                        exception_listener=_exception_listener(),
                    ),
                ),
            ],
        )
    )

    _ = await dispatcher.dispatch(RequestEvent(make_message(path="/api/books"), bag))

    assert seen == [session]


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
