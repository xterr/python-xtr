"""Sends the client identifier and secret as HTTP Basic credentials."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.oauth2 import ClientSecretBasic


def test_an_empty_secret_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = ClientSecretBasic("")

    assert str(raised.value) == (
        "The OAuth2 client secret cannot be empty. Use NoClientAuthentication "
        "to declare a public client, which holds no secret."
    )


def test_the_credentials_are_built_from_the_identifier_and_the_secret() -> None:
    method = ClientSecretBasic("s3cret")

    options = method.authenticate("my-client", "https://issuer.example/token", {})

    assert options["auth_basic"] == "my-client:s3cret"


def test_the_identifier_and_the_secret_are_each_percent_encoded() -> None:
    method = ClientSecretBasic("p@ss:word")

    options = method.authenticate("my client", "https://issuer.example/token", {})

    assert options["auth_basic"] == "my%20client:p%40ss%3Aword"


def test_the_rest_of_the_options_is_kept() -> None:
    method = ClientSecretBasic("s3cret")
    options: dict[str, object] = {"max_redirects": 0, "body": {"grant_type": "refresh_token"}}

    prepared = method.authenticate("my-client", "https://issuer.example/token", options)

    assert prepared["max_redirects"] == 0
    assert prepared["body"] == {"grant_type": "refresh_token"}
    assert prepared["auth_basic"] == "my-client:s3cret"


def test_the_method_is_client_secret_basic() -> None:
    assert ClientSecretBasic("s3cret").get_method() == "client_secret_basic"
