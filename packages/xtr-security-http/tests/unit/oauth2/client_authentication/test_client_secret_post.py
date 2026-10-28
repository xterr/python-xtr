"""Sends the client secret in the body of the token request."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.oauth2 import ClientSecretPost


def test_an_empty_secret_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = ClientSecretPost("")

    assert str(raised.value) == (
        "The OAuth2 client secret cannot be empty. Use NoClientAuthentication "
        "to declare a public client, which holds no secret."
    )


def test_the_secret_is_added_to_the_token_request_body() -> None:
    method = ClientSecretPost("s3cret")
    options: dict[str, object] = {"body": {"client_id": "my-client"}}

    prepared = method.authenticate("my-client", "https://issuer.example/token", options)

    assert prepared["body"] == {"client_id": "my-client", "client_secret": "s3cret"}


def test_a_missing_body_is_created_for_the_secret() -> None:
    method = ClientSecretPost("s3cret")

    prepared = method.authenticate("my-client", "https://issuer.example/token", {})

    assert prepared["body"] == {"client_secret": "s3cret"}


def test_the_method_is_client_secret_post() -> None:
    assert ClientSecretPost("s3cret").get_method() == "client_secret_post"
