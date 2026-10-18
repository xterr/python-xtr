"""The firewall runs a matched request's chain over the lifecycle's events."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_http_foundation import PathRequestMatcher
from xtr_http_kernel import ExceptionEvent, FinishRequestEvent, RequestEvent
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_security_core.authentication.authentication_trust_resolver import (
    AuthenticationTrustResolver,
)
from xtr_security_core.exception import BadCredentialsError

from tests.support.contexts import FakeFirewallContext
from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.firewall.abstract_listener import AbstractListener
from xtr_security_http.firewall.exception_listener import ExceptionListener
from xtr_security_http.firewall.firewall import Firewall
from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from starlette.responses import Response as FrameworkResponse
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_http.firewall.firewall_listener_interface import (
        FirewallListenerInterface,
    )

pytestmark = pytest.mark.anyio


class _Step(AbstractListener):
    """A chain step that records its asks, answering as it was built to."""

    def __init__(
        self,
        name: str,
        log: list[str],
        *,
        supports_answer: bool | None = None,
        answer: FrameworkResponse | None = None,
    ) -> None:
        """Record under ``name`` onto ``log``, answering as this step is built to."""
        self._name: str = name
        self._log: list[str] = log
        self._supports_answer: bool | None = supports_answer
        self._answer: FrameworkResponse | None = answer
        self.supports_calls: list[ServerRequestInterface] = []

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        """Record the ask, and answer as this step was built to."""
        self.supports_calls.append(request)
        self._log.append(f"{self._name} supports")
        return self._supports_answer

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        """Record the ask, answering the request when this step was built to."""
        self._log.append(f"{self._name} authenticate")
        if self._answer is not None:
            request_event.set_response(self._answer)


@final
class _CleanupStep(_Step):
    """A cleanup step, behind the default-priority steps."""

    __slots__ = ()

    @staticmethod
    @override
    def get_priority() -> int:
        """Return the chain position: behind the default-priority steps."""
        return -100


@final
class _LogoutStep(_Step):
    """The logout step, at the position the chain inserts it at."""

    __slots__ = ()

    @staticmethod
    @override
    def get_priority() -> int:
        """Return the chain position: behind the default, ahead of the access step."""
        return -127


@final
class _AccessStep(_Step):
    """The access step, last among the steps that decide."""

    __slots__ = ()

    @staticmethod
    @override
    def get_priority() -> int:
        """Return the chain position: behind authentication and the cleanup steps."""
        return -255


def _firewall(
    *chain: FirewallListenerInterface,
    exception_listener: ExceptionListener | None = None,
    logout_listener: FirewallListenerInterface | None = None,
    matcher: str = "^/",
) -> FirewallMap:
    """Return a map of one firewall carrying the chain and listeners given."""
    return FirewallMap(
        [
            (
                PathRequestMatcher(matcher),
                FakeFirewallContext(
                    name="api",
                    authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                    access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                    listeners=tuple(chain),
                    exception_listener=exception_listener,
                    logout_listener=logout_listener,
                ),
            ),
        ],
    )


def _exception_listener() -> ExceptionListener:
    """Return the listener a secured firewall stores for its requests."""
    return ExceptionListener(
        AuthenticationTrustResolver(), ResponseFactory(), StarletteHttpFactory()
    )


def test_it_satisfies_the_subscriber_interface() -> None:
    assert isinstance(Firewall(_firewall()), EventSubscriberInterface)


def test_it_subscribes_to_the_lifecycle_events_at_the_firewalls_priorities() -> None:
    declared = Firewall.get_subscribed_events()

    assert declared[RequestEvent] == ("on_request", 8)
    assert declared[ExceptionEvent] == ("on_exception", 1)
    assert declared[FinishRequestEvent] == "on_finish_request"


async def test_it_skips_a_step_only_on_a_strict_false_supports() -> None:
    log: list[str] = []
    firewall = Firewall(
        _firewall(
            _Step("refusing", log, supports_answer=False),
            _Step("lazy", log, supports_answer=None),
            _Step("eager", log, supports_answer=True),
        ),
    )

    await firewall.on_request(RequestEvent(make_message(), {}))

    assert log == [
        "refusing supports",
        "lazy supports",
        "lazy authenticate",
        "eager supports",
        "eager authenticate",
    ]


async def test_it_breaks_the_chain_when_a_step_answered_the_request() -> None:
    log: list[str] = []
    event = RequestEvent(make_message(), {})
    firewall = Firewall(
        _firewall(
            _Step("answering", log, answer=ResponseFactory().create_response(401)),
            _Step("later", log),
        ),
    )

    await firewall.on_request(event)

    assert log == ["answering supports", "answering authenticate"]
    assert event.response is not None
    assert event.response.status_code == 401


async def test_it_runs_the_chain_in_the_order_the_map_left_it() -> None:
    log: list[str] = []
    # The order the bundle's sorting pass leaves a chain in: the
    # default-priority step ahead of the access step at -255.
    firewall = Firewall(_firewall(_Step("manager", log), _AccessStep("access", log)))

    await firewall.on_request(RequestEvent(make_message(), {}))

    assert log == [
        "manager supports",
        "manager authenticate",
        "access supports",
        "access authenticate",
    ]


async def test_it_hands_supports_the_request_carrying_the_events_state_bag() -> None:
    log: list[str] = []
    step = _Step("manager", log)
    bag: dict[str, object] = {}
    firewall = Firewall(_firewall(step))

    await firewall.on_request(RequestEvent(make_message(), bag))

    assert state_bag_of(step.supports_calls[0]) is bag


async def test_it_inserts_the_logout_step_before_the_first_lower_priority_step() -> None:
    log: list[str] = []
    # Two steps run below the logout's -127: the logout joins ahead of the
    # first of them, once — not again before the second.
    firewall = Firewall(
        _firewall(
            _Step("manager", log),
            _CleanupStep("cleanup", log),
            _AccessStep("first", log),
            _AccessStep("second", log),
            logout_listener=_LogoutStep("logout", log),
        ),
    )

    await firewall.on_request(RequestEvent(make_message(), {}))

    assert log == [
        "manager supports",
        "manager authenticate",
        "cleanup supports",
        "cleanup authenticate",
        "logout supports",
        "logout authenticate",
        "first supports",
        "first authenticate",
        "second supports",
        "second authenticate",
    ]


async def test_it_appends_the_logout_step_when_no_chain_step_runs_lower() -> None:
    log: list[str] = []
    firewall = Firewall(
        _firewall(
            _Step("manager", log),
            _CleanupStep("cleanup", log),
            logout_listener=_LogoutStep("logout", log),
        ),
    )

    await firewall.on_request(RequestEvent(make_message(), {}))

    assert log == [
        "manager supports",
        "manager authenticate",
        "cleanup supports",
        "cleanup authenticate",
        "logout supports",
        "logout authenticate",
    ]


async def test_it_leaves_an_equal_priority_step_ahead_of_the_logout_step() -> None:
    log: list[str] = []
    firewall = Firewall(
        _firewall(
            _LogoutStep("equal", log),
            _AccessStep("access", log),
            logout_listener=_LogoutStep("logout", log),
        ),
    )

    await firewall.on_request(RequestEvent(make_message(), {}))

    assert log == [
        "equal supports",
        "equal authenticate",
        "logout supports",
        "logout authenticate",
        "access supports",
        "access authenticate",
    ]


async def test_it_parks_the_matched_firewalls_exception_listener_on_the_requests_carrier() -> None:
    listener = _exception_listener()
    bag: dict[str, object] = {}
    firewall = Firewall(_firewall(exception_listener=listener))

    await firewall.on_request(RequestEvent(make_message(), bag))

    assert (
        security_state_of(bag).attributes[SecurityRequestAttributes.EXCEPTION_LISTENER] is listener
    )


async def test_it_parks_the_matched_firewall_on_the_requests_carrier() -> None:
    bag: dict[str, object] = {}
    firewall = Firewall(_firewall())

    await firewall.on_request(RequestEvent(make_message(), bag))

    context = security_state_of(bag).firewall_context
    assert context is not None
    assert context.name == "api"


async def test_it_parks_nothing_when_no_firewall_matches() -> None:
    bag: dict[str, object] = {}
    firewall = Firewall(_firewall(matcher="^/api"))

    await firewall.on_request(RequestEvent(make_message(path="/public"), bag))

    assert SecurityRequestAttributes.EXCEPTION_LISTENER not in security_state_of(bag).attributes
    assert security_state_of(bag).firewall_context is None


async def test_it_routes_an_exception_to_the_requests_stored_listener() -> None:
    bag: dict[str, object] = {}
    firewall = Firewall(_firewall(exception_listener=_exception_listener()))
    await firewall.on_request(RequestEvent(make_message(), bag))
    event = ExceptionEvent(make_message(), bag, BadCredentialsError())

    await firewall.on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401
    assert event.response.headers["WWW-Authenticate"] == "Bearer"


async def test_it_leaves_an_exception_alone_when_no_listener_was_stored() -> None:
    event = ExceptionEvent(make_message(), {}, RuntimeError("boom"))

    await Firewall(_firewall()).on_exception(event)

    assert event.response is None


async def test_no_stored_listener_reaches_the_next_request() -> None:
    first_bag: dict[str, object] = {}
    second_bag: dict[str, object] = {}
    firewall = Firewall(_firewall(exception_listener=_exception_listener()))
    await firewall.on_request(RequestEvent(make_message(), first_bag))

    second = ExceptionEvent(make_message(), second_bag, BadCredentialsError())
    await firewall.on_exception(second)

    assert second.response is None


async def test_finish_request_clears_the_stored_listener() -> None:
    bag: dict[str, object] = {}
    firewall = Firewall(_firewall(exception_listener=_exception_listener()))
    await firewall.on_request(RequestEvent(make_message(), bag))

    await firewall.on_finish_request(FinishRequestEvent(make_message(), bag))

    assert SecurityRequestAttributes.EXCEPTION_LISTENER not in security_state_of(bag).attributes


async def test_finish_request_without_a_stored_listener_is_a_no_op() -> None:
    bag: dict[str, object] = {}
    firewall = Firewall(_firewall())

    await firewall.on_finish_request(FinishRequestEvent(make_message(), bag))

    assert security_state_of(bag).attributes == {}
