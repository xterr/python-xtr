"""The login-failure event holds its context and sets a response."""

from __future__ import annotations

from xtr_security_core.exception import BadCredentialsError

from tests.support.http import FakeAccessTokenHandler
from tests.support.requests import make_request
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.event.login_failure_event import LoginFailureEvent


def test_it_holds_its_context_and_sets_a_response() -> None:
    error = BadCredentialsError()
    request = make_request()
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}), HeaderAccessTokenExtractor()
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
