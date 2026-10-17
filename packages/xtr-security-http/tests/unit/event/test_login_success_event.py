"""The login-success event holds its context and replaces the response."""

from __future__ import annotations

import inspect

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.null_token import NullToken

from tests.support.http import FakeAccessTokenHandler
from tests.support.messages import make_message
from tests.support.users import loader
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.debug.traceable_authenticator import TraceableAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.event.login_success_event import LoginSuccessEvent

pytestmark = pytest.mark.anyio


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


def test_the_constructor_signature_is_aligned_with_the_upstream_order() -> None:
    names = list(inspect.signature(LoginSuccessEvent.__init__).parameters)

    assert names == [
        "self",
        "authenticator",
        "passport",
        "token",
        "request",
        "response",
        "firewall_name",
        "previous_token",
    ]


def test_it_carries_the_token_the_storage_held_before() -> None:
    previous = NullToken()
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
        previous,
    )

    assert event.get_previous_token() is previous


async def test_get_user_loads_the_passports_user() -> None:
    badge = UserBadge("alice", user_loader=loader())
    _ = await badge.get_user()
    event = LoginSuccessEvent(
        AccessTokenAuthenticator(
            FakeAccessTokenHandler({}),
            HeaderAccessTokenExtractor(),
            ResponseFactory(),
        ),
        Passport(badge),
        NullToken(),
        make_message(),
        None,
        "api",
    )

    assert event.get_user().get_user_identifier() == "alice"


def test_a_traceable_wrapper_is_opened_by_the_authenticator_getter() -> None:
    inner = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )
    event = LoginSuccessEvent(
        TraceableAuthenticator(inner),
        Passport(UserBadge("alice")),
        NullToken(),
        make_message(),
        None,
        "api",
    )

    assert event.get_authenticator() is inner
