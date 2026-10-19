"""The conditions listener: whether a successful login asked to be remembered."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_security_core.exception import AuthenticationError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from xtr_security_http.authenticator.passport.badge.remember_me_badge import RememberMeBadge
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import (
    SelfValidatingPassport,
)
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.event_listener import CheckRememberMeConditionsListener

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


def _success_event(
    request: ServerRequestInterface,
    *,
    badge: RememberMeBadge | None = None,
) -> LoginSuccessEvent:
    """Build a successful login whose passport carries ``badge``, when one is given."""
    badges = [] if badge is None else [badge]
    passport = SelfValidatingPassport(UserBadge("ada"), badges)
    token = PostAuthenticationToken(InMemoryUser("ada"), "main", ())
    return LoginSuccessEvent(_FakeAuthenticator(), passport, token, request, None, "main")


async def _dispatch(listener: CheckRememberMeConditionsListener, event: Event) -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(listener)
    _ = await dispatcher.dispatch(event)


async def test_a_passport_without_the_badge_is_left_alone() -> None:
    badge = RememberMeBadge()
    listener = CheckRememberMeConditionsListener()

    await _dispatch(listener, _success_event(make_message(), badge=None))

    assert badge.is_enabled() is False


async def test_always_remember_me_enables_the_badge_without_asking_the_request() -> None:
    badge = RememberMeBadge()
    listener = CheckRememberMeConditionsListener({"always_remember_me": True})

    await _dispatch(listener, _success_event(make_message(), badge=badge))

    assert badge.is_enabled() is True


async def test_the_requests_form_field_asks_to_be_remembered() -> None:
    badge = RememberMeBadge()
    listener = CheckRememberMeConditionsListener()
    request = make_message(
        method="POST",
        parsed_body={"_remember_me": "true"},
    )

    await _dispatch(listener, _success_event(request, badge=badge))

    assert badge.is_enabled() is True


async def test_the_requests_query_asks_to_be_remembered() -> None:
    badge = RememberMeBadge()
    listener = CheckRememberMeConditionsListener()
    request = make_message(query="_remember_me=1")

    await _dispatch(listener, _success_event(request, badge=badge))

    assert badge.is_enabled() is True


async def test_the_badges_own_word_outranks_the_requests() -> None:
    badge = RememberMeBadge({"_remember_me": "1"})
    listener = CheckRememberMeConditionsListener()
    request = make_message(method="POST", parsed_body={"_remember_me": "0"})

    await _dispatch(listener, _success_event(request, badge=badge))

    assert badge.is_enabled() is True


async def test_a_form_field_that_does_not_ask_leaves_the_badge_disabled() -> None:
    badge = RememberMeBadge()
    listener = CheckRememberMeConditionsListener()
    request = make_message(method="POST", parsed_body={"_remember_me": "0"})

    await _dispatch(listener, _success_event(request, badge=badge))

    assert badge.is_enabled() is False


async def test_a_get_request_is_not_read_for_a_form_field() -> None:
    badge = RememberMeBadge()
    listener = CheckRememberMeConditionsListener()
    request = make_message(method="GET", parsed_body={"_remember_me": "true"})

    await _dispatch(listener, _success_event(request, badge=badge))

    assert badge.is_enabled() is False


async def test_every_spelling_that_asks_is_accepted() -> None:
    for asking in ("1", "true", "on", "yes", "TRUE", "On"):
        badge = RememberMeBadge()
        listener = CheckRememberMeConditionsListener()
        request = make_message(method="POST", parsed_body={"_remember_me": asking})

        await _dispatch(listener, _success_event(request, badge=badge))

        assert badge.is_enabled() is True, asking


async def test_every_spelling_that_does_not_ask_is_refused() -> None:
    for not_asking in ("", "0", "false", "off", "no", "maybe", "2"):
        badge = RememberMeBadge()
        listener = CheckRememberMeConditionsListener()
        request = make_message(method="POST", parsed_body={"_remember_me": not_asking})

        await _dispatch(listener, _success_event(request, badge=badge))

        assert badge.is_enabled() is False, not_asking


def test_the_subscribed_events_run_ahead_of_the_listener_that_sets_the_cookie() -> None:
    assert CheckRememberMeConditionsListener.get_subscribed_events() == {
        LoginSuccessEvent: ("on_login_success", -32),
    }
