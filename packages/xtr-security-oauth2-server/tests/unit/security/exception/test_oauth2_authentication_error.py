"""A presented access token that did not establish a caller."""

from __future__ import annotations

from http import HTTPStatus

from xtr_security_core.exception import AuthenticationError

from xtr_security_oauth2_server.exception.oauth2_error import OAuth2Error
from xtr_security_oauth2_server.security.exception.oauth2_authentication_error import (
    OAuth2AuthenticationError,
)

INTERNAL = "the token named a client that no longer exists"


def test_it_is_answered_by_the_firewall() -> None:
    # The firewall only answers the family's own failures.
    assert isinstance(OAuth2AuthenticationError(INTERNAL, 401), AuthenticationError)


def test_one_except_still_catches_everything_this_package_raises() -> None:
    assert isinstance(OAuth2AuthenticationError(INTERNAL, 401), OAuth2Error)


def test_the_status_the_refusal_is_answered_with_is_carried() -> None:
    refused = OAuth2AuthenticationError(INTERNAL, HTTPStatus.FORBIDDEN)

    assert refused.get_status_code() == HTTPStatus.FORBIDDEN


def test_it_always_suggests_presenting_a_bearer_token() -> None:
    # This server accepts its access tokens in no other way, so that is the
    # whole of what it can suggest.
    assert OAuth2AuthenticationError(INTERNAL, 401).get_headers() == {
        "WWW-Authenticate": "Bearer",
    }


def test_the_internal_message_is_not_what_a_caller_is_shown() -> None:
    # It may name the token, the client or the reason, so it is never sent.
    refused = OAuth2AuthenticationError(INTERNAL, 401)

    assert str(refused) == INTERNAL
    assert refused.get_message_key() == OAuth2AuthenticationError.MESSAGE_KEY
    assert INTERNAL not in refused.get_message_key()


def test_a_deployment_may_name_the_public_text_itself() -> None:
    refused = OAuth2AuthenticationError(INTERNAL, 401, message_key="Nope.")

    assert refused.get_message_key() == "Nope."
