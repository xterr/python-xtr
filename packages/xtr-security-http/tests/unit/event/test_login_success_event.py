"""The login-success event holds its context and replaces the response."""

from __future__ import annotations

from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.null_token import NullToken

from tests.support.http import FakeAccessTokenHandler
from tests.support.messages import make_message
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.event.login_success_event import LoginSuccessEvent


def test_it_holds_its_context_and_replaces_the_response() -> None:
    passport = Passport(UserBadge("alice"))
    token = NullToken()
    request = make_message()
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}), HeaderAccessTokenExtractor(), ResponseFactory()
    )

    event = LoginSuccessEvent(authenticator, passport, token, request, None, "api")

    assert event.get_authenticator() is authenticator
    assert event.get_passport() is passport
    assert event.get_authenticated_token() is token
    assert event.get_request() is request
    assert event.get_response() is None
    assert event.get_firewall_name() == "api"

    event.set_response(None)
    assert event.get_response() is None


def test_a_listener_may_replace_the_response() -> None:
    response = ResponseFactory().create_response(200)
    event = LoginSuccessEvent(
        AccessTokenAuthenticator(
            FakeAccessTokenHandler({}),
            HeaderAccessTokenExtractor(),
            ResponseFactory(),
        ),
        Passport(UserBadge("alice")),
        NullToken(),
        make_message(),
        None,
        "api",
    )

    event.set_response(response)

    assert event.get_response() is response
