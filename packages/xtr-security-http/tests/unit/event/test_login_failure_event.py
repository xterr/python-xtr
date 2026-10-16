"""The login-failure event holds its context and sets a response."""

from __future__ import annotations

from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.exception import BadCredentialsError

from tests.support.http import FakeAccessTokenHandler
from tests.support.messages import make_message
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.event.login_failure_event import LoginFailureEvent


def test_it_holds_its_context_and_sets_a_response() -> None:
    error = BadCredentialsError()
    request = make_message()
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}), HeaderAccessTokenExtractor(), ResponseFactory()
    )

    event = LoginFailureEvent(error, authenticator, request, None, "api")

    assert event.get_exception() is error
    assert event.get_authenticator() is authenticator
    assert event.get_request() is request
    assert event.get_passport() is None
    assert event.get_firewall_name() == "api"
    assert event.get_response() is None

    event.set_response(None)
    assert event.get_response() is None


def test_a_listener_may_answer_the_failure() -> None:
    response = ResponseFactory().create_response(401)
    event = LoginFailureEvent(
        BadCredentialsError(),
        AccessTokenAuthenticator(
            FakeAccessTokenHandler({}),
            HeaderAccessTokenExtractor(),
            ResponseFactory(),
        ),
        make_message(),
        None,
        "api",
    )

    event.set_response(response)

    assert event.get_response() is response
