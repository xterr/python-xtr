"""The event announcing a session token was logged out by its refresh."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.token_deauthenticated_event import TokenDeauthenticatedEvent


def test_it_carries_the_original_token_the_request_and_the_reason() -> None:
    token = PostAuthenticationToken(InMemoryUser("ada"), "main", roles=())
    request = make_message(path="/account")
    reason = AuthenticationError("The account was disabled.")

    event = TokenDeauthenticatedEvent(token, request, "the user has changed", (dict,), reason)

    assert event.get_original_token() is token
    assert event.get_request() is request
    assert event.get_reason() == "the user has changed"
    assert event.get_provider_classes() == (dict,)
    assert event.get_exception() is reason


def test_the_reason_the_providers_and_the_error_are_optional() -> None:
    token = PostAuthenticationToken(InMemoryUser("ada"), "main", roles=())
    request = make_message()

    event = TokenDeauthenticatedEvent(token, request)

    assert event.get_reason() is None
    assert event.get_provider_classes() == ()
    assert event.get_exception() is None
