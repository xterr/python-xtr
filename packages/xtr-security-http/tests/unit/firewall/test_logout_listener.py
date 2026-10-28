"""The chain step that logs a request out, through the logout event."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_event_dispatcher import EventDispatcher, EventSubscriberInterface
from xtr_http_kernel import RequestEvent
from xtr_http_kernel.bridge import Response as DualResponse
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_http_message import HttpFactory
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_csrf import CsrfTokenManagerInterface
from xtr_security_csrf.csrf_token import CsrfToken

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.exception import LogoutError
from xtr_security_http.firewall.abstract_listener import AbstractListener
from xtr_security_http.firewall.firewall import _chain_with_logout
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface
from xtr_security_http.firewall.logout_listener import LogoutListener
from xtr_security_http.http_utils import HttpUtils

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

pytestmark = pytest.mark.anyio


@final
class _RecordingTokenStorage:
    """A token storage that answers what it was set, recording every set."""

    __slots__ = ("_token", "sets")

    def __init__(self, token: TokenInterface | None = None) -> None:
        self._token = token
        self.sets: list[TokenInterface | None] = []

    def get_token(self) -> TokenInterface | None:
        """Return the token this storage was built with, or last set to."""
        return self._token

    def set_token(self, token: TokenInterface | None) -> None:
        """Record the set, and answer it from now on."""
        self._token = token
        self.sets.append(token)


@final
class _RecordingManager:
    """A cross-site request forgery manager that answers what it was built with."""

    __slots__ = ("_valid", "asked")

    def __init__(self, valid: bool = True) -> None:
        self._valid = valid
        self.asked: list[CsrfToken] = []

    async def get_token(self, token_id: str) -> CsrfToken:
        """Mint a token under ``token_id``; the logout listener never mints."""
        return CsrfToken(token_id, "minted")

    async def refresh_token(self, token_id: str) -> CsrfToken:
        """Mint a fresh value; the logout listener never refreshes."""
        return CsrfToken(token_id, "refreshed")

    async def remove_token(self, token_id: str) -> str | None:
        """Drop the token; the logout listener never removes."""
        del token_id
        return None

    async def is_token_valid(self, token: CsrfToken) -> bool:
        """Record the ask, and answer what this manager was built with."""
        self.asked.append(token)
        return self._valid


@final
class _AnsweringSubscriber(EventSubscriberInterface):
    """A logout listener that answers the event with a response, recording what it saw."""

    __slots__ = ("response", "seen")

    def __init__(self, response: ResponseInterface | None = None) -> None:
        self.response = response
        self.seen: list[LogoutEvent] = []

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to the logout event."""
        return {LogoutEvent: "on_logout"}

    async def on_logout(self, event: LogoutEvent) -> None:
        """Record the event, and answer it when this listener was built with a response."""
        self.seen.append(event)
        if self.response is not None:
            event.set_response(self.response)


def _token() -> PostAuthenticationToken:
    return PostAuthenticationToken(InMemoryUser("ada", roles=()), "main", ())


def _step(name: str, priority: int) -> FirewallListenerInterface:
    """Build a chain step that names itself and runs at ``priority``."""

    @final
    class Step(AbstractListener):
        """A chain step that only reports its name and position."""

        __slots__ = ()

        @staticmethod
        @override
        def get_priority() -> int:
            return priority

        @override
        async def supports(self, request: ServerRequestInterface) -> bool | None:
            del request
            return None

        @override
        async def authenticate(self, request_event: RequestEvent) -> None:
            del request_event

    Step.__name__ = Step.__qualname__ = f"_Step_{name}"
    return Step()


def _listener(
    storage: _RecordingTokenStorage,
    dispatcher: EventDispatcher,
    manager: _RecordingManager | None = None,
    *,
    logout_path: str = "/logout",
) -> LogoutListener:
    """Build the step over a storage and a dispatcher, with the given logout path."""
    return LogoutListener(
        storage,
        HttpUtils(ResponseFactory()),
        dispatcher,
        StarletteHttpFactory(),
        manager,
        logout_path=logout_path,
    )


def _request(path: str = "/logout", parsed_body: object | None = None) -> ServerRequestInterface:
    return make_message(path=path, parsed_body=parsed_body)


def test_it_satisfies_the_interface() -> None:
    listener = _listener(_RecordingTokenStorage(), EventDispatcher())

    assert isinstance(listener, FirewallListenerInterface)


def test_the_recording_manager_satisfies_the_manager_interface() -> None:
    assert isinstance(_RecordingManager(), CsrfTokenManagerInterface)


def test_its_priority_is_minus_127() -> None:
    assert LogoutListener.get_priority() == -127


async def test_supports_answers_true_for_the_configured_logout_path() -> None:
    answer = await _listener(_RecordingTokenStorage(), EventDispatcher()).supports(
        _request("/logout")
    )

    assert answer is True


async def test_supports_answers_a_strict_false_for_another_path() -> None:
    answer = await _listener(_RecordingTokenStorage(), EventDispatcher()).supports(
        _request("/login")
    )

    assert answer is False


async def test_supports_matches_the_path_the_listener_was_configured_with() -> None:
    answer = await _listener(
        _RecordingTokenStorage(), EventDispatcher(), logout_path="/bye"
    ).supports(_request("/bye"))

    assert answer is True


async def test_a_logout_request_is_announced_on_the_firewalls_dispatcher() -> None:
    token = _token()
    storage = _RecordingTokenStorage(token)
    dispatcher = EventDispatcher()
    answering = _AnsweringSubscriber()
    dispatcher.add_subscriber(answering)
    request = _request()

    await _listener(storage, dispatcher).authenticate(RequestEvent(request, {}))

    (event,) = answering.seen
    assert event.get_request() is request
    assert event.get_token() is token


async def test_the_event_is_announced_before_the_token_is_cleared() -> None:
    """A listener of the logout event still reads the token being logged out."""
    storage = _RecordingTokenStorage(_token())
    dispatcher = EventDispatcher()
    answering = _AnsweringSubscriber()
    dispatcher.add_subscriber(answering)

    await _listener(storage, dispatcher).authenticate(RequestEvent(_request(), {}))

    assert answering.seen[0].get_token() is not None


async def test_a_logout_clears_the_token_on_the_storage_and_the_state() -> None:
    storage = _RecordingTokenStorage(_token())
    state_bag: dict[str, object] = {}
    event = RequestEvent(_request(), state_bag)
    security_state_of(state_bag).token = _token()

    await _listener(storage, EventDispatcher()).authenticate(event)

    assert storage.sets == [None]
    assert storage.get_token() is None
    assert security_state_of(state_bag).token is None


async def test_a_response_the_event_carries_is_set_on_the_request_event() -> None:
    storage = _RecordingTokenStorage(_token())
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(_AnsweringSubscriber(HttpFactory().create_response(204)))
    event = RequestEvent(_request(), {})

    await _listener(storage, dispatcher).authenticate(event)

    assert event.response is not None
    assert event.response.status_code == 204


async def test_a_kernel_response_the_event_carries_is_set_as_it_is() -> None:
    storage = _RecordingTokenStorage(_token())
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(_AnsweringSubscriber(ResponseFactory().create_response(204)))
    event = RequestEvent(_request(), {})

    await _listener(storage, dispatcher).authenticate(event)

    assert isinstance(event.response, DualResponse)


async def test_a_logout_no_listener_answered_leaves_the_request_unanswered() -> None:
    storage = _RecordingTokenStorage(_token())
    event = RequestEvent(_request(), {})

    await _listener(storage, EventDispatcher()).authenticate(event)

    assert event.response is None


async def test_a_valid_forgery_token_in_the_payload_passes_the_proof() -> None:
    manager = _RecordingManager(valid=True)
    request = _request(parsed_body={"_csrf_token": "carried"})

    await _listener(_RecordingTokenStorage(), EventDispatcher(), manager).authenticate(
        RequestEvent(request, {})
    )

    (asked,) = manager.asked
    assert asked.get_id() == "logout"
    assert asked.get_value() == "carried"


async def test_a_forgery_token_in_the_query_string_passes_the_proof() -> None:
    manager = _RecordingManager(valid=True)
    request = make_message(path="/logout", query="_csrf_token=carried")

    await _listener(_RecordingTokenStorage(), EventDispatcher(), manager).authenticate(
        RequestEvent(request, {})
    )

    (asked,) = manager.asked
    assert asked.get_value() == "carried"


async def test_an_invalid_forgery_token_refuses_the_logout() -> None:
    manager = _RecordingManager(valid=False)
    request = _request(parsed_body={"_csrf_token": "forged"})

    with pytest.raises(LogoutError) as caught:
        await _listener(_RecordingTokenStorage(), EventDispatcher(), manager).authenticate(
            RequestEvent(request, {})
        )

    assert "Invalid CSRF token." in str(caught.value)


async def test_a_missing_forgery_token_refuses_the_logout() -> None:
    manager = _RecordingManager(valid=True)

    with pytest.raises(LogoutError):
        await _listener(_RecordingTokenStorage(), EventDispatcher(), manager).authenticate(
            RequestEvent(_request(), {})
        )


async def test_a_forgery_token_that_is_not_text_refuses_the_logout() -> None:
    manager = _RecordingManager(valid=True)
    request = _request(parsed_body={"_csrf_token": ["not", "text"]})

    with pytest.raises(LogoutError):
        await _listener(_RecordingTokenStorage(), EventDispatcher(), manager).authenticate(
            RequestEvent(request, {})
        )


async def test_the_proof_reads_the_parameter_and_id_the_listener_was_configured_with() -> None:
    manager = _RecordingManager(valid=True)
    listener = LogoutListener(
        _RecordingTokenStorage(),
        HttpUtils(ResponseFactory()),
        EventDispatcher(),
        StarletteHttpFactory(),
        manager,
        csrf_parameter="proof",
        csrf_token_id="bye",  # noqa: S106 -- a token id in a test, not a credential
    )

    await listener.authenticate(RequestEvent(_request(parsed_body={"proof": "carried"}), {}))

    (asked,) = manager.asked
    assert asked.get_id() == "bye"
    assert asked.get_value() == "carried"


async def test_no_manager_wired_means_no_proof_asked() -> None:
    storage = _RecordingTokenStorage(_token())

    await _listener(storage, EventDispatcher()).authenticate(RequestEvent(_request(), {}))

    assert storage.sets == [None]


def test_the_chain_inserts_the_logout_step_ahead_of_the_lower_priority_steps() -> None:
    """The firewall's insertion rule: the logout runs before the steps below -127."""
    context = _step("context", 0)
    manager_step = _step("manager", 0)
    access = _step("access", -255)
    logout = _listener(_RecordingTokenStorage(), EventDispatcher())

    chain = list(_chain_with_logout((context, manager_step, access), logout))

    assert chain == [context, manager_step, logout, access]


def test_the_chain_leaves_a_logout_free_chain_untouched() -> None:
    context = _step("context", 0)
    access = _step("access", -255)

    chain = list(_chain_with_logout((context, access), None))

    assert chain == [context, access]
