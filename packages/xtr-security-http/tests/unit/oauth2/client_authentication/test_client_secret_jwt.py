"""Authenticates the client with an assertion signed with its secret."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from joserfc import jwt
from joserfc.jwk import OctKey
from xtr_clock import MockClock
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.oauth2.client_authentication.client_secret_jwt import ClientSecretJwt

NOW = 1_000_000
SECRET = "a-shared-secret-of-thirty-two-bytes!"  # noqa: S105 -- test material, not a credential
TWENTY_BYTES = "a-secret-of-precisely-twenty"


def test_an_empty_secret_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = ClientSecretJwt("")

    assert str(raised.value) == (
        "The OAuth2 client secret cannot be empty. Use NoClientAuthentication "
        "to declare a public client, which holds no secret."
    )


def test_a_secret_shorter_than_the_digest_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = ClientSecretJwt(TWENTY_BYTES)

    assert str(raised.value) == (
        'The OAuth2 client secret cannot key a "client_secret_jwt" assertion '
        'signed with "HS256", which asks for at least 32 bytes '
        "(RFC 7518, Section 3.2). Ask the provider for a longer secret, or "
        'authenticate the client with "PrivateKeyJwt".'
    )


def test_a_secret_shorter_than_a_longer_digest_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = ClientSecretJwt(SECRET, algorithm="HS384")


def test_an_algorithm_outside_the_mac_family_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = ClientSecretJwt(SECRET, algorithm="RS256")

    assert str(raised.value) == (
        'The "RS256" algorithm cannot sign a "client_secret_jwt" client assertion. '
        'Use one of "HS256", "HS384", "HS512".'
    )


def test_the_assertion_is_signed_with_the_secret_as_the_hmac_key() -> None:
    assertion = ClientSecretJwt(SECRET, clock=MockClock(datetime.fromtimestamp(NOW, UTC)))

    prepared = assertion.authenticate("my-client", "https://issuer.example/token", {})

    body = cast("dict[str, object]", prepared["body"])
    token = body["client_assertion"]
    assert isinstance(token, str)
    decoded = jwt.decode(token, OctKey.import_key(SECRET))
    assert decoded.header["alg"] == "HS256"
    assert decoded.claims["iss"] == "my-client"
    assert decoded.claims["iat"] == NOW


def test_the_method_is_client_secret_jwt() -> None:
    assert ClientSecretJwt(SECRET).get_method() == "client_secret_jwt"
