"""Sends no client credentials, for a public client."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.oauth2 import NoClientAuthentication


def test_the_method_is_none() -> None:
    assert NoClientAuthentication().get_method() == "none"


def test_a_request_that_redeems_no_code_passes_through_unchanged() -> None:
    options: dict[str, object] = {
        "body": {"grant_type": "refresh_token", "refresh_token": "the-token"},
        "max_redirects": 0,
    }

    assert (
        NoClientAuthentication().authenticate(
            "my-client",
            "https://issuer.example/token",
            options,
        )
        is options
    )


def test_an_authorization_code_without_a_verifier_is_refused() -> None:
    options: dict[str, object] = {
        "body": {"grant_type": "authorization_code", "code": "the-code"},
    }

    with pytest.raises(InvalidArgumentError) as raised:
        _ = NoClientAuthentication().authenticate(
            "my-client",
            "https://issuer.example/token",
            options,
        )

    assert str(raised.value) == (
        "A public OAuth2 client must exchange the authorization code with PKCE, "
        "as it sends no client secret. Pass the code verifier with the code "
        "exchange, or authenticate the client with a secret."
    )


def test_a_code_without_a_grant_type_is_refused_all_the_same() -> None:
    options: dict[str, object] = {"body": {"code": "the-code"}}

    with pytest.raises(InvalidArgumentError):
        _ = NoClientAuthentication().authenticate(
            "my-client",
            "https://issuer.example/token",
            options,
        )


def test_an_empty_verifier_is_refused_all_the_same() -> None:
    options: dict[str, object] = {
        "body": {
            "grant_type": "authorization_code",
            "code": "the-code",
            "code_verifier": "",
        },
    }

    with pytest.raises(InvalidArgumentError):
        _ = NoClientAuthentication().authenticate(
            "my-client",
            "https://issuer.example/token",
            options,
        )


def test_an_authorization_code_with_a_verifier_passes() -> None:
    options: dict[str, object] = {
        "body": {
            "grant_type": "authorization_code",
            "code": "the-code",
            "code_verifier": "the-verifier",
        },
    }

    assert (
        NoClientAuthentication().authenticate(
            "my-client",
            "https://issuer.example/token",
            options,
        )
        is options
    )


def test_a_request_with_no_body_passes_through() -> None:
    prepared = NoClientAuthentication().authenticate(
        "my-client",
        "https://issuer.example/token",
        {},
    )
    assert prepared == {}
