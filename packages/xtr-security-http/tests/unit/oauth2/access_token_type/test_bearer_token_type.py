"""The bearer token of RFC 6750, which is used by whoever holds it."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.oauth2 import BearerTokenType

if TYPE_CHECKING:
    from xtr_http_client_contracts import HttpResponseInterface


@final
class _Response:
    """A response the bearer type reads nothing of."""


def test_the_token_type_is_bearer() -> None:
    assert BearerTokenType().get_token_type() == "Bearer"


def test_a_response_naming_no_token_type_is_accepted() -> None:
    BearerTokenType().check_token_response({})
    BearerTokenType().check_token_response({"token_type": ""})


def test_a_response_naming_bearer_is_accepted_case_insensitively() -> None:
    BearerTokenType().check_token_response({"token_type": "Bearer"})
    BearerTokenType().check_token_response({"token_type": "bearer"})


def test_a_response_naming_another_token_type_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        BearerTokenType().check_token_response({"token_type": "DPoP"})

    assert str(raised.value) == (
        'The OIDC provider issued an access token of the "DPoP" type, which this '
        "client cannot use: it presents bearer tokens (RFC 6749, Section 7.1)."
    )


def test_a_response_naming_a_non_string_token_type_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        BearerTokenType().check_token_response({"token_type": 123})


def test_the_token_request_options_are_prepared_unchanged() -> None:
    options: dict[str, object] = {"body": {"grant_type": "authorization_code"}}

    assert (
        BearerTokenType().prepare_token_request(
            "https://issuer.example/token",
            options,
        )
        is options
    )


def test_the_token_is_presented_as_the_bearer_credential() -> None:
    options: dict[str, object] = {"headers": {"Accept": "application/json"}}

    prepared = BearerTokenType().present_token(
        "the-access-token",
        "GET",
        "https://resource.example/orders",
        options,
    )

    assert prepared["auth_bearer"] == "the-access-token"
    assert prepared["headers"] == {"Accept": "application/json"}


def test_a_response_never_asks_for_a_second_round() -> None:
    assert (
        BearerTokenType().on_response(
            cast("HttpResponseInterface", cast("object", _Response())),
            "https://resource.example/orders",
        )
        is False
    )
