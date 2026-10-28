"""The remember-me listener: the cookie a login earned, and the endings that drop it."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_security_core.exception import AuthenticationError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from tests.support.remember_me import RecordingHandler
from xtr_security_http.authenticator.passport.badge.remember_me_badge import RememberMeBadge
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import (
    SelfValidatingPassport,
)
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.event.login_failure_event import LoginFailureEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.event.token_deauthenticated_event import TokenDeauthenticatedEvent
from xtr_security_http.event_listener import RememberMeListener

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Event
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.authenticator.passport.passport import Passport

pytestmark = pytest.mark.anyio


@final
class _FakeAuthenticator:
    """An authenticator that is only ever carried by an event, never run."""

    __slots__ = ()

    def supports(self, request: ServerRequestInterface) -> bool | None:
        del request
        return False

    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        del request
        raise AuthenticationError("Never reached.")

    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
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


def _load_user(identifier: str) -> InMemoryUser:
    """Load the identifier as the user the login's token settles on."""
    return InMemoryUser(identifier)


async def _success_event(
    request: ServerRequestInterface,
    *,
    badge: RememberMeBadge | None = None,
) -> LoginSuccessEvent:
    """Build a successful login whose passport carries ``badge``, its user loaded.

    The manager loads the passport's user before the login-success event is
    dispatched, so the listener reading the event's user finds one; the test
    mirrors that.
    """
    badges = [] if badge is None else [badge]
    passport = SelfValidatingPassport(UserBadge("ada", user_loader=_load_user), badges)
    _ = await passport.get_user()
    token = PostAuthenticationToken(InMemoryUser("ada"), "main", ())
    return LoginSuccessEvent(_FakeAuthenticator(), passport, token, request, None, "main")


async def _dispatch(listener: RememberMeListener, event: Event) -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(listener)
    _ = await dispatcher.dispatch(event)


async def test_an_enabled_badge_clears_the_old_cookie_and_sets_a_new_one() -> None:
    handler = RecordingHandler()
    request = make_message()
    badge = RememberMeBadge().enable()

    await _dispatch(RememberMeListener(handler), await _success_event(request, badge=badge))

    assert handler.cleared == [request]
    assert len(handler.created) == 1
    assert handler.created[0][0] is request
    assert handler.created[0][1].get_user_identifier() == "ada"


async def test_a_disabled_badge_clears_the_old_cookie_and_stages_nothing_new() -> None:
    handler = RecordingHandler()
    request = make_message()
    badge = RememberMeBadge()

    await _dispatch(RememberMeListener(handler), await _success_event(request, badge=badge))

    assert handler.cleared == [request]
    assert handler.created == []


async def test_a_passport_without_the_badge_touches_nothing() -> None:
    handler = RecordingHandler()

    await _dispatch(RememberMeListener(handler), await _success_event(make_message()))

    assert handler.cleared == []
    assert handler.created == []
    assert handler.consumed == []


async def test_a_failed_login_clears_the_cookie() -> None:
    handler = RecordingHandler()
    request = make_message()

    await _dispatch(
        RememberMeListener(handler),
        LoginFailureEvent(AuthenticationError("No."), _FakeAuthenticator(), request, None, "main"),
    )

    assert handler.cleared == [request]


async def test_a_logout_clears_the_cookie() -> None:
    handler = RecordingHandler()
    request = make_message()

    await _dispatch(RememberMeListener(handler), LogoutEvent(request, None))

    assert handler.cleared == [request]


async def test_a_deauthentication_clears_the_cookie() -> None:
    handler = RecordingHandler()
    request = make_message()
    token = PostAuthenticationToken(InMemoryUser("ada"), "main", ())

    await _dispatch(
        RememberMeListener(handler),
        TokenDeauthenticatedEvent(original_token=token, request=request),
    )

    assert handler.cleared == [request]


def test_the_subscribed_events_answer_the_login_and_its_endings() -> None:
    assert RememberMeListener.get_subscribed_events() == {
        LoginSuccessEvent: ("on_login_success", -64),
        LoginFailureEvent: "clear_cookie",
        LogoutEvent: "clear_cookie",
        TokenDeauthenticatedEvent: "clear_cookie",
    }
