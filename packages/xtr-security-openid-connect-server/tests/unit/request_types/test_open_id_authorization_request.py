"""The authorization request a sign-in carries, beside everything the flow fills in."""

from __future__ import annotations

import pytest
from xtr_security_oauth2_server_core.request_types.authorization_request import AuthorizationRequest

from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)
from xtr_security_openid_connect_server.request_types.open_id_authorization_request import (
    OpenIdAuthorizationRequest,
)


def test_it_is_the_authorization_request_the_flow_fills_in() -> None:
    request = OpenIdAuthorizationRequest()
    request.set_state("xyz")

    assert isinstance(request, AuthorizationRequest)
    assert request.get_state() == "xyz"


def test_it_carries_no_nonce_until_one_is_set() -> None:
    assert OpenIdAuthorizationRequest().get_nonce() is None


def test_it_hands_back_the_nonce_it_was_given() -> None:
    request = OpenIdAuthorizationRequest()
    request.set_nonce("n-0S6_WzA2Mj")

    assert request.get_nonce() == "n-0S6_WzA2Mj"


def test_it_forgets_a_nonce_set_back_to_none() -> None:
    request = OpenIdAuthorizationRequest()
    request.set_nonce("n-0S6_WzA2Mj")
    request.set_nonce(None)

    assert request.get_nonce() is None


def test_it_carries_no_prompt_until_one_is_set() -> None:
    assert OpenIdAuthorizationRequest().get_prompt() == frozenset()


def test_it_hands_back_the_prompt_it_was_given() -> None:
    request = OpenIdAuthorizationRequest()
    request.set_prompt(frozenset({"login", "consent"}))

    assert request.get_prompt() == frozenset({"login", "consent"})


def test_it_carries_no_max_age_until_one_is_set() -> None:
    assert OpenIdAuthorizationRequest().get_max_age() is None


def test_it_hands_back_the_max_age_it_was_given() -> None:
    request = OpenIdAuthorizationRequest()
    request.set_max_age(600)

    assert request.get_max_age() == 600


def test_it_keeps_a_max_age_of_zero() -> None:
    # Zero is an age, not an absent one: it asks for a sign-in made just now.
    request = OpenIdAuthorizationRequest()
    request.set_max_age(0)

    assert request.get_max_age() == 0


def test_it_forgets_a_max_age_set_back_to_none() -> None:
    request = OpenIdAuthorizationRequest()
    request.set_max_age(600)
    request.set_max_age(None)

    assert request.get_max_age() is None


def test_a_negative_max_age_is_refused() -> None:
    request = OpenIdAuthorizationRequest()

    with pytest.raises(InvalidArgumentError, match="max_age"):
        request.set_max_age(-1)


def test_a_refused_max_age_leaves_the_one_set_before() -> None:
    request = OpenIdAuthorizationRequest()
    request.set_max_age(600)

    with pytest.raises(InvalidArgumentError):
        request.set_max_age(-1)

    assert request.get_max_age() == 600


def test_it_carries_no_auth_time_until_one_is_set() -> None:
    assert OpenIdAuthorizationRequest().get_auth_time() is None


def test_it_hands_back_the_auth_time_it_was_given() -> None:
    request = OpenIdAuthorizationRequest()
    request.set_auth_time(1_772_600_767)

    assert request.get_auth_time() == 1_772_600_767


def test_it_forgets_an_auth_time_set_back_to_none() -> None:
    request = OpenIdAuthorizationRequest()
    request.set_auth_time(1_772_600_767)
    request.set_auth_time(None)

    assert request.get_auth_time() is None


def test_its_reading_holds_no_nonce() -> None:
    # The nonce is what ties an ID token to the browser session that asked for
    # it, so it stays out of a log line, as the state does.
    request = OpenIdAuthorizationRequest()
    request.set_grant_type_id("authorization_code")
    request.set_nonce("n-0S6_WzA2Mj")

    assert "n-0S6_WzA2Mj" not in repr(request)
