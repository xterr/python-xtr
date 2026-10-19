"""The manager listener delegates each question to the firewall's manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from starlette.responses import Response as FrameworkResponse
from xtr_http_kernel import RequestEvent
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_http_message import Response as PureResponse

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.exception import MissingStateBagError
from xtr_security_http.firewall.authenticator_manager_listener import AuthenticatorManagerListener
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_http._security_state import SecurityState

pytestmark = pytest.mark.anyio


@final
class _Manager:
    """Answers each question with what it was built to, recording what it was asked."""

    def __init__(self, *, response: ResponseInterface | None = None) -> None:
        self._response = response
        self.supports_calls: list[tuple[ServerRequestInterface, SecurityState]] = []
        self.authenticate_calls: list[tuple[ServerRequestInterface, SecurityState]] = []

    def supports(self, request: ServerRequestInterface, state: SecurityState) -> bool | None:
        """Record the ask, and answer that any authenticator applies."""
        self.supports_calls.append((request, state))
        return True

    async def authenticate_request(
        self, request: ServerRequestInterface, state: SecurityState
    ) -> ResponseInterface | None:
        """Record the ask, and answer the response this manager was built with."""
        self.authenticate_calls.append((request, state))
        return self._response


def _listener(manager: _Manager) -> AuthenticatorManagerListener:
    return AuthenticatorManagerListener(manager, StarletteHttpFactory())


def _asked(bag: dict[str, object]) -> ServerRequestInterface:
    """Return a request carrying the event's state bag, as the chain's caller asks about it."""
    return make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)


def test_it_satisfies_the_interface() -> None:
    assert isinstance(_listener(_Manager()), FirewallListenerInterface)


def test_its_priority_is_the_chains_default() -> None:
    assert AuthenticatorManagerListener.get_priority() == 0


async def test_supports_delegates_to_the_manager_with_the_carrier_from_the_events_state_bag() -> (
    None
):
    bag: dict[str, object] = {}
    state = security_state_of(bag)
    manager = _Manager()
    request = _asked(bag)

    answer = await _listener(manager).supports(request)

    assert answer is True
    assert manager.supports_calls == [(request, state)]


async def test_supports_refuses_a_request_no_state_bag_was_parked_on() -> None:
    with pytest.raises(MissingStateBagError):
        _ = await _listener(_Manager()).supports(make_message())


async def test_authenticate_delegates_with_the_carrier_from_the_events_state_bag() -> None:
    bag: dict[str, object] = {}
    state = security_state_of(bag)
    manager = _Manager()
    event = RequestEvent(make_message(), bag)

    await _listener(manager).authenticate(event)

    ((handed, handed_state),) = manager.authenticate_calls
    assert handed_state is state
    assert handed.get_attribute(SecurityRequestAttributes.STATE_BAG) is bag


async def test_authenticate_hands_the_manager_a_request_carrying_the_events_state_bag() -> None:
    bag: dict[str, object] = {}
    _ = security_state_of(bag)
    manager = _Manager()
    event = RequestEvent(make_message(), bag)

    await _listener(manager).authenticate(event)

    ((handed, _state),) = manager.authenticate_calls
    assert handed.get_attribute(SecurityRequestAttributes.STATE_BAG) is bag
    assert event.request.get_attribute(SecurityRequestAttributes.STATE_BAG) is None


async def test_authenticate_hands_the_manager_the_same_security_state_the_bag_carries() -> None:
    bag: dict[str, object] = {}
    state = security_state_of(bag)
    manager = _Manager()

    await _listener(manager).authenticate(RequestEvent(make_message(), bag))

    ((handed, handed_state),) = manager.authenticate_calls
    assert handed_state is state
    assert security_state_of(state_bag_of(handed)) is state


async def test_authenticate_sets_the_bridged_response_when_the_manager_answers_one() -> None:
    pure = PureResponse(401, None, None, "1.1").with_header("location", "/login")
    event = RequestEvent(make_message(), {})

    await _listener(_Manager(response=pure)).authenticate(event)

    assert event.response is not None
    assert event.response is not pure
    assert isinstance(event.response, FrameworkResponse)
    assert event.response.status_code == 401
    assert event.response.headers["location"] == "/login"


async def test_authenticate_sends_a_kernel_response_as_it_is() -> None:
    dual = ResponseFactory().create_response(401).with_header("location", "/login")
    event = RequestEvent(make_message(), {})

    await _listener(_Manager(response=dual)).authenticate(event)

    assert event.response is dual


async def test_authenticate_leaves_the_event_untouched_when_the_manager_answers_none() -> None:
    event = RequestEvent(make_message(), {})

    await _listener(_Manager(response=None)).authenticate(event)

    assert event.response is None
