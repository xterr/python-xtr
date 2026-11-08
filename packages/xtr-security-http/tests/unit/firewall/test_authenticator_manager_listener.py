"""The manager listener delegates each question to the firewall's manager."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, final

import pytest
from starlette.responses import Response as FrameworkResponse
from xtr_http_kernel import RequestEvent
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_http_message import Response as PureResponse

from tests.support.messages import make_message
from tests.support.served import served_message
from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.exception import MissingStateBagError
from xtr_security_http.firewall.authenticator_manager_listener import AuthenticatorManagerListener
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_http._security_state import SecurityState

pytestmark = pytest.mark.anyio

_FORM = "application/x-www-form-urlencoded"
_CREDENTIALS = b"_username=alice&_password=secret"


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


def _handed_form(manager: _Manager) -> object | None:
    """Return what the request the manager was handed answers as its parsed body."""
    ((handed, _state),) = manager.authenticate_calls
    return handed.get_parsed_body()


async def test_authenticate_hands_the_manager_the_form_a_post_submitted() -> None:
    manager = _Manager()
    request, _channel = served_message("POST", "/login_check", _CREDENTIALS, content_type=_FORM)

    await _listener(manager).authenticate(RequestEvent(request, {}))

    form = _handed_form(manager)
    assert isinstance(form, Mapping)
    assert dict(form) == {"_username": "alice", "_password": "secret"}  # pyright: ignore[reportUnknownArgumentType] -- a form maps names to what was sent


async def test_authenticate_hands_the_manager_a_multipart_form_a_post_submitted() -> None:
    manager = _Manager()
    body = b'--b\r\nContent-Disposition: form-data; name="_username"\r\n\r\nalice\r\n--b--\r\n'
    request, _channel = served_message(
        "POST", "/login_check", body, content_type="multipart/form-data; boundary=b"
    )

    await _listener(manager).authenticate(RequestEvent(request, {}))

    form = _handed_form(manager)
    assert isinstance(form, Mapping)
    assert dict(form) == {"_username": "alice"}  # pyright: ignore[reportUnknownArgumentType] -- a form maps names to what was sent


async def test_authenticate_leaves_the_body_readable_after_reading_the_form() -> None:
    request, _channel = served_message("POST", "/login_check", _CREDENTIALS, content_type=_FORM)

    await _listener(_Manager()).authenticate(RequestEvent(request, {}))

    assert await request.get_body().get_contents() == _CREDENTIALS


async def test_authenticate_reads_no_body_of_a_request_that_is_no_posted_form() -> None:
    request, channel = served_message("POST", "/api", b'{"a": 1}', content_type="application/json")

    await _listener(_Manager()).authenticate(RequestEvent(request, {}))

    assert channel.reads == 0


async def test_authenticate_reads_no_body_of_a_content_type_only_starting_like_a_form() -> None:
    request, channel = served_message(
        "POST", "/login_check", _CREDENTIALS, content_type="application/x-www-form-urlencodedX"
    )

    await _listener(_Manager()).authenticate(RequestEvent(request, {}))

    assert channel.reads == 0


async def test_authenticate_reads_no_body_of_a_get() -> None:
    request, channel = served_message("GET", "/login_check", content_type=_FORM)

    await _listener(_Manager()).authenticate(RequestEvent(request, {}))

    assert channel.reads == 0


async def test_authenticate_keeps_a_form_the_request_already_carries() -> None:
    manager = _Manager()
    form = {"_username": "alice"}
    request = make_message(method="POST", headers={"Content-Type": _FORM}, parsed_body=form)

    await _listener(manager).authenticate(RequestEvent(request, {}))

    assert _handed_form(manager) == form
