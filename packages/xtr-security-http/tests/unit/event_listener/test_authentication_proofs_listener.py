"""The authentication proofs listener: record a login's methods, carry them across logins."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_clock import MockClock
from xtr_event_dispatcher import EventDispatcher
from xtr_security_core.authentication.authentication_method import AuthenticationMethod
from xtr_security_core.authentication.token.remember_me_token import RememberMeToken
from xtr_security_core.exception import AuthenticationError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from xtr_security_http.authenticator.passport.badge.authentication_method_badge import (
    AuthenticationMethodBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import (
    SelfValidatingPassport,
)
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.event_listener import AuthenticationProofsListener
from xtr_security_http.event_listener.authentication_proofs_listener import PRIORITY

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Event
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.passport import Passport

pytestmark = pytest.mark.anyio

_NOW = 1_700_000_000
_FROZEN = "2023-11-14T22:13:20+00:00"


@final
class _InteractiveAuthenticator:
    """An authenticator that reports itself interactive, carried by an event and never run."""

    __slots__ = ()

    def is_interactive(self) -> bool:
        return True

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


@final
class _NonInteractiveAuthenticator:
    """An authenticator that does not announce its logins as the user's own act."""

    __slots__ = ()

    def is_interactive(self) -> bool:
        return False

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


@final
class _NotInteractiveAtAll:
    """An authenticator that does not implement the interactive interface at all."""

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


def _token(user_identifier: str = "ada") -> PostAuthenticationToken:
    return PostAuthenticationToken(InMemoryUser(user_identifier), "main", ())


def _event(
    authenticator: AuthenticatorInterface,
    *,
    token: TokenInterface | None = None,
    badge: AuthenticationMethodBadge | None = None,
    previous_token: TokenInterface | None = None,
) -> LoginSuccessEvent:
    badges = [] if badge is None else [badge]
    passport = SelfValidatingPassport(UserBadge("ada"), badges)
    return LoginSuccessEvent(
        authenticator,
        passport,
        _token() if token is None else token,
        make_message(),
        None,
        "main",
        previous_token,
    )


async def _dispatch(listener: AuthenticationProofsListener, event: Event) -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(listener)
    _ = await dispatcher.dispatch(event)


def _listener() -> AuthenticationProofsListener:
    return AuthenticationProofsListener(MockClock(_FROZEN))


async def test_an_interactive_login_records_its_stated_methods() -> None:
    token = _token()
    badge = AuthenticationMethodBadge(
        AuthenticationMethod.PASSWORD,
        AuthenticationMethod.ONE_TIME_PASSWORD,
    )

    await _dispatch(_listener(), _event(_InteractiveAuthenticator(), token=token, badge=badge))

    assert dict(token.get_authentication_proofs()) == {
        AuthenticationMethod.PASSWORD: _NOW,
        AuthenticationMethod.ONE_TIME_PASSWORD: _NOW,
    }


async def test_a_stated_method_is_recorded_on_a_token_that_already_holds_it() -> None:
    token = _token()
    token.set_authentication_proofs({AuthenticationMethod.PASSWORD: 1})
    badge = AuthenticationMethodBadge(AuthenticationMethod.PASSWORD)

    await _dispatch(_listener(), _event(_InteractiveAuthenticator(), token=token, badge=badge))

    assert dict(token.get_authentication_proofs()) == {AuthenticationMethod.PASSWORD: _NOW}


async def test_an_interactive_login_without_a_badge_records_an_unspecified_method() -> None:
    token = _token()

    await _dispatch(_listener(), _event(_InteractiveAuthenticator(), token=token))

    assert dict(token.get_authentication_proofs()) == {AuthenticationMethod.UNSPECIFIED: _NOW}


async def test_an_unstated_method_does_not_overwrite_proofs_the_authenticator_recorded() -> None:
    token = _token()
    token.set_authentication_proofs({AuthenticationMethod.FACE: 7})

    await _dispatch(_listener(), _event(_InteractiveAuthenticator(), token=token))

    assert dict(token.get_authentication_proofs()) == {AuthenticationMethod.FACE: 7}


async def test_a_non_interactive_login_records_nothing() -> None:
    token = _token()
    badge = AuthenticationMethodBadge(AuthenticationMethod.PASSWORD)

    await _dispatch(_listener(), _event(_NonInteractiveAuthenticator(), token=token, badge=badge))

    assert dict(token.get_authentication_proofs()) == {}


async def test_a_non_interactive_authenticator_type_records_nothing() -> None:
    token = _token()

    await _dispatch(_listener(), _event(_NotInteractiveAtAll(), token=token))

    assert dict(token.get_authentication_proofs()) == {}


async def test_a_remember_me_login_records_nothing() -> None:
    user = InMemoryUser("ada")
    token = RememberMeToken(user, "main")
    badge = AuthenticationMethodBadge(AuthenticationMethod.PASSWORD)

    await _dispatch(_listener(), _event(_InteractiveAuthenticator(), token=token, badge=badge))

    assert dict(token.get_authentication_proofs()) == {}


async def test_the_previous_tokens_proofs_are_carried_over_for_the_same_user() -> None:
    previous = _token()
    previous.set_authentication_proofs({AuthenticationMethod.ONE_TIME_PASSWORD: 5})
    token = _token()

    await _dispatch(
        _listener(),
        _event(_NonInteractiveAuthenticator(), token=token, previous_token=previous),
    )

    assert dict(token.get_authentication_proofs()) == {AuthenticationMethod.ONE_TIME_PASSWORD: 5}


async def test_the_newer_entry_wins_when_a_proof_is_carried_over() -> None:
    previous = _token()
    previous.set_authentication_proofs({AuthenticationMethod.PASSWORD: 5})
    token = _token()
    badge = AuthenticationMethodBadge(AuthenticationMethod.PASSWORD)

    await _dispatch(
        _listener(),
        _event(_InteractiveAuthenticator(), token=token, badge=badge, previous_token=previous),
    )

    assert dict(token.get_authentication_proofs()) == {AuthenticationMethod.PASSWORD: _NOW}


async def test_proofs_are_not_carried_over_from_a_different_user() -> None:
    previous = _token("grace")
    previous.set_authentication_proofs({AuthenticationMethod.ONE_TIME_PASSWORD: 5})
    token = _token("ada")

    await _dispatch(
        _listener(),
        _event(_NonInteractiveAuthenticator(), token=token, previous_token=previous),
    )

    assert dict(token.get_authentication_proofs()) == {}


async def test_no_previous_token_carries_nothing_over() -> None:
    token = _token()

    await _dispatch(_listener(), _event(_NonInteractiveAuthenticator(), token=token))

    assert dict(token.get_authentication_proofs()) == {}


async def test_a_previous_token_with_no_proofs_carries_nothing_over() -> None:
    previous = _token()
    token = _token()

    await _dispatch(
        _listener(),
        _event(_NonInteractiveAuthenticator(), token=token, previous_token=previous),
    )

    assert dict(token.get_authentication_proofs()) == {}


def test_the_listener_subscribes_to_the_login_success_event_at_its_priority() -> None:
    assert AuthenticationProofsListener.get_subscribed_events() == {
        LoginSuccessEvent: ("on_login_success", 256),
    }
    assert PRIORITY == 256
