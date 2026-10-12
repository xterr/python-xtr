"""The authorization request starts empty, is filled in, and shows little."""

from __future__ import annotations

from typing import final

import pytest

from tests.support.entities import make_client, make_scopes, make_user
from xtr_security_oauth2_server_core.exception import InvalidArgumentError
from xtr_security_oauth2_server_core.request_types.authorization_request import AuthorizationRequest
from xtr_security_oauth2_server_core.request_types.authorization_request_interface import (
    AuthorizationRequestInterface,
)


@final
class _RequestCarryingANonce(AuthorizationRequest):
    """What an add-on writes to remember one more thing about the original request."""

    def __init__(self) -> None:
        super().__init__()
        self._nonce: str | None = None

    def get_nonce(self) -> str | None:
        return self._nonce

    def set_nonce(self, nonce: str) -> None:
        self._nonce = nonce


def test_it_declares_the_authorization_request_contract() -> None:
    assert AuthorizationRequestInterface in AuthorizationRequest.__mro__


def test_an_extension_may_extend_it_to_carry_a_parameter_of_its_own() -> None:
    # The seam an add-on reaches through. The request is the one piece of state
    # that crosses the consent step, so an extension remembering a parameter of
    # the original one extends this and hands its own back from
    # create_authorization_request() — rather than reimplementing the whole
    # contract to add a field.
    client = make_client()
    request = _RequestCarryingANonce()
    request.set_nonce("n-0S6_WzA2Mj")
    request.set_client(client)

    assert request.get_nonce() == "n-0S6_WzA2Mj"
    # Everything the server fills in goes on working, which is the point of
    # extending rather than replacing.
    assert request.get_client() is client
    assert isinstance(request, AuthorizationRequestInterface)


def test_it_is_not_approved_until_the_resource_owner_approves_it() -> None:
    assert AuthorizationRequest().is_authorization_approved() is False


def test_it_names_no_resource_owner_until_one_is_set() -> None:
    assert AuthorizationRequest().get_user() is None


def test_it_carries_no_scopes_until_some_are_set() -> None:
    assert AuthorizationRequest().get_scopes() == ()


def test_it_names_no_redirect_uri_until_one_is_set() -> None:
    assert AuthorizationRequest().get_redirect_uri() is None


def test_it_carries_no_state_until_one_is_set() -> None:
    assert AuthorizationRequest().get_state() is None


def test_it_carries_no_code_challenge_until_one_is_set() -> None:
    request = AuthorizationRequest()

    assert request.get_code_challenge() is None
    assert request.get_code_challenge_method() is None


def test_reading_a_grant_type_nobody_set_refuses() -> None:
    with pytest.raises(InvalidArgumentError, match="grant"):
        _ = AuthorizationRequest().get_grant_type_id()


def test_reading_a_client_nobody_set_refuses() -> None:
    with pytest.raises(InvalidArgumentError, match="client"):
        _ = AuthorizationRequest().get_client()


def test_it_hands_back_the_grant_type_it_was_given() -> None:
    request = AuthorizationRequest()
    request.set_grant_type_id("authorization_code")

    assert request.get_grant_type_id() == "authorization_code"


def test_it_hands_back_the_client_it_was_given() -> None:
    client = make_client()
    request = AuthorizationRequest()
    request.set_client(client)

    assert request.get_client() is client


def test_it_hands_back_the_resource_owner_it_was_given() -> None:
    user = make_user()
    request = AuthorizationRequest()
    request.set_user(user)

    assert request.get_user() is user


def test_it_keeps_the_scopes_in_the_order_they_were_set() -> None:
    request = AuthorizationRequest()
    request.set_scopes(make_scopes("write", "read"))

    assert [scope.get_identifier() for scope in request.get_scopes()] == ["write", "read"]


def test_the_scopes_it_hands_back_do_not_change_when_the_caller_changes_its_list() -> None:
    requested = list(make_scopes("read"))
    request = AuthorizationRequest()
    request.set_scopes(requested)
    requested.clear()

    assert len(request.get_scopes()) == 1


def test_it_hands_back_the_approval_it_was_given() -> None:
    request = AuthorizationRequest()
    request.set_authorization_approved(True)

    assert request.is_authorization_approved() is True


def test_it_hands_back_the_redirect_uri_it_was_given() -> None:
    request = AuthorizationRequest()
    request.set_redirect_uri("https://client.example.com/callback")

    assert request.get_redirect_uri() == "https://client.example.com/callback"


def test_it_forgets_a_redirect_uri_set_back_to_none() -> None:
    request = AuthorizationRequest()
    request.set_redirect_uri("https://client.example.com/callback")
    request.set_redirect_uri(None)

    assert request.get_redirect_uri() is None


def test_it_hands_back_the_state_it_was_given() -> None:
    request = AuthorizationRequest()
    request.set_state("opaque-state")

    assert request.get_state() == "opaque-state"


def test_it_hands_back_the_code_challenge_it_was_given() -> None:
    request = AuthorizationRequest()
    request.set_code_challenge("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
    request.set_code_challenge_method("S256")

    assert request.get_code_challenge() == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    assert request.get_code_challenge_method() == "S256"


def test_its_reading_names_the_grant_and_the_approval() -> None:
    request = AuthorizationRequest()
    request.set_grant_type_id("authorization_code")

    assert repr(request) == (
        "AuthorizationRequest(grant_type_id='authorization_code', authorization_approved=False)"
    )


def test_its_reading_holds_neither_the_state_nor_the_code_challenge() -> None:
    request = AuthorizationRequest()
    request.set_grant_type_id("authorization_code")
    request.set_state("opaque-state")
    request.set_code_challenge("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    reading = repr(request)

    assert "opaque-state" not in reading
    assert "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM" not in reading
