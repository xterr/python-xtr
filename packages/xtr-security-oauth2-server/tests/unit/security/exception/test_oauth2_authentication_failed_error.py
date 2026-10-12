"""The one refusal the resource-server side actually raises."""

from __future__ import annotations

from http import HTTPStatus

from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.security.exception.oauth2_authentication_error import (
    OAuth2AuthenticationError,
)
from xtr_security_oauth2_server.security.exception.oauth2_authentication_failed_error import (
    OAuth2AuthenticationFailedError,
)

INTERNAL = "The resource server rejected the request."


def test_whatever_went_wrong_is_the_same_unauthorized_answer() -> None:
    # A caller presenting a token that will not work learns only that: saying
    # which of the reasons it was would let it probe what this server holds.
    assert OAuth2AuthenticationFailedError.create(INTERNAL).get_status_code() == (
        HTTPStatus.UNAUTHORIZED
    )


def test_it_is_one_of_the_refusals_the_firewall_answers() -> None:
    assert isinstance(
        OAuth2AuthenticationFailedError.create(INTERNAL),
        OAuth2AuthenticationError,
    )


def test_the_protocol_refusal_that_led_here_is_kept_as_the_cause() -> None:
    # A log shows which reason it was, even though the caller is not told.
    cause = OAuthServerError.access_denied()

    refused = OAuth2AuthenticationFailedError.create(INTERNAL, cause)

    assert refused.__cause__ is cause


def test_nothing_is_attached_when_no_cause_was_given() -> None:
    assert OAuth2AuthenticationFailedError.create(INTERNAL).__cause__ is None


def test_the_internal_message_is_kept_apart_from_the_public_text() -> None:
    refused = OAuth2AuthenticationFailedError.create(INTERNAL)

    assert str(refused) == INTERNAL
    assert refused.get_message_key() == OAuth2AuthenticationFailedError.MESSAGE_KEY


def test_it_challenges_for_a_bearer_token() -> None:
    assert OAuth2AuthenticationFailedError.create(INTERNAL).get_headers() == {
        "WWW-Authenticate": "Bearer",
    }
