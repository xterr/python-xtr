"""The listener that hands a successful login to the firewall's session strategy."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.exception import AuthenticationError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authenticator.passport import SelfValidatingPassport
from xtr_security_http.authenticator.passport.badge import UserBadge
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.login_failure_event import LoginFailureEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.event_listener import SessionStrategyListener
from xtr_security_http.security_request_attributes import SecurityRequestAttributes
from xtr_security_http.session import SessionAuthenticationStrategyInterface

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Event
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.authenticator.passport import Passport

pytestmark = pytest.mark.anyio


@final
class _RecordingStrategy:
    """A session strategy that records the logins it is handed."""

    __slots__ = ("calls",)

    def __init__(self) -> None:
        self.calls: list[tuple[ServerRequestInterface, TokenInterface]] = []

    async def on_authentication(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> None:
        self.calls.append((request, token))


def test_the_recording_strategy_satisfies_the_interface() -> None:
    assert isinstance(_RecordingStrategy(), SessionAuthenticationStrategyInterface)


@final
class _OtherToken(AbstractToken):
    """A token of another class, for the comparison that weighs the class."""

    __slots__ = ()


@final
class _PlainUser:
    """A user that names itself and nothing else, for any identifier a test needs."""

    __slots__ = ("_identifier",)

    def __init__(self, identifier: str) -> None:
        self._identifier = identifier

    def get_user_identifier(self) -> str:
        return self._identifier

    def get_roles(self) -> tuple[str, ...]:
        return ()


@final
class _FakeAuthenticator:
    """An authenticator that is only ever carried by an event, never run."""

    __slots__ = ()

    def supports(self, request: ServerRequestInterface) -> bool | None:
        del request
        return False

    async def authenticate(self, request: ServerRequestInterface) -> SelfValidatingPassport:
        del request
        raise AuthenticationError("Never reached.")

    async def create_token(
        self,
        passport: Passport,
        firewall_name: str,
    ) -> TokenInterface:
        del passport, firewall_name
        raise AuthenticationError("Never reached.")

    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
        firewall_name: str,
    ) -> None:
        del request, token, firewall_name

    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> None:
        del request, error


def _token(identifier: str = "ada") -> PostAuthenticationToken:
    return PostAuthenticationToken(InMemoryUser(identifier, roles=()), "main", ())


def _other_token(identifier: str = "ada") -> _OtherToken:
    token = _OtherToken()
    token.set_user(_PlainUser(identifier))
    return token


def _success_event(
    request: ServerRequestInterface,
    token: TokenInterface,
    previous_token: TokenInterface | None = None,
) -> LoginSuccessEvent:
    return LoginSuccessEvent(
        _FakeAuthenticator(),
        SelfValidatingPassport(UserBadge("carried")),
        token,
        request,
        None,
        "main",
        previous_token,
    )


def _request_with_session() -> ServerRequestInterface:
    """Build a request whose security state carries the session a stateful firewall parks."""
    bag: dict[str, object] = {}
    message = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = Session(
        MemorySessionStorage()
    )
    return message


async def _dispatch(listener: SessionStrategyListener, event: Event) -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(listener)
    _ = await dispatcher.dispatch(event)


async def test_a_successful_login_hands_the_request_and_token_to_the_strategy() -> None:
    strategy = _RecordingStrategy()
    request = _request_with_session()
    token = _token()

    await _dispatch(SessionStrategyListener(strategy), _success_event(request, token))

    assert strategy.calls == [(request, token)]


async def test_a_login_without_a_session_never_reaches_the_strategy() -> None:
    strategy = _RecordingStrategy()
    request = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, {})

    await _dispatch(SessionStrategyListener(strategy), _success_event(request, _token()))

    assert strategy.calls == []


async def test_a_login_of_a_request_without_a_state_bag_never_reaches_the_strategy() -> None:
    strategy = _RecordingStrategy()

    await _dispatch(SessionStrategyListener(strategy), _success_event(make_message(), _token()))

    assert strategy.calls == []


async def test_a_re_authentication_of_the_same_account_is_skipped() -> None:
    strategy = _RecordingStrategy()
    request = _request_with_session()

    await _dispatch(
        SessionStrategyListener(strategy),
        _success_event(request, _token("ada"), previous_token=_token("ada")),
    )

    assert strategy.calls == []


async def test_a_login_of_another_account_reaches_the_strategy() -> None:
    strategy = _RecordingStrategy()
    request = _request_with_session()
    token = _token("grace")

    await _dispatch(
        SessionStrategyListener(strategy),
        _success_event(request, token, previous_token=_token("ada")),
    )

    assert strategy.calls == [(request, token)]


async def test_the_same_account_through_another_token_class_reaches_the_strategy() -> None:
    strategy = _RecordingStrategy()
    request = _request_with_session()
    token = _other_token("ada")

    await _dispatch(
        SessionStrategyListener(strategy),
        _success_event(request, token, previous_token=_token("ada")),
    )

    assert strategy.calls == [(request, token)]


async def test_a_login_of_an_empty_identifier_reaches_the_strategy() -> None:
    strategy = _RecordingStrategy()
    request = _request_with_session()
    token = _other_token("")

    await _dispatch(
        SessionStrategyListener(strategy),
        _success_event(request, token, previous_token=_other_token("")),
    )

    assert strategy.calls == [(request, token)]


async def test_a_failed_login_never_reaches_the_strategy() -> None:
    strategy = _RecordingStrategy()
    request = _request_with_session()

    await _dispatch(
        SessionStrategyListener(strategy),
        LoginFailureEvent(
            AuthenticationError("No."),
            _FakeAuthenticator(),
            request,
            None,
            "main",
        ),
    )

    assert strategy.calls == []


def test_the_subscribed_events_listen_to_the_login_success_event() -> None:
    assert SessionStrategyListener.get_subscribed_events() == {
        LoginSuccessEvent: "on_login_success"
    }
