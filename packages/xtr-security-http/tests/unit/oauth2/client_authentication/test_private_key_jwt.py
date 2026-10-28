"""Authenticates the client with an assertion signed by its private key."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from joserfc import jwt
from joserfc.jwk import ECKey, RSAKey
from xtr_clock import MockClock
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.oauth2.client_authentication.private_key_jwt import PrivateKeyJwt

NOW = 1_000_000


def _private_key() -> RSAKey:
    return RSAKey.generate_key(2048, parameters={"kid": "k1"})


def test_an_algorithm_outside_the_asymmetric_family_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = PrivateKeyJwt(_private_key(), algorithm="HS256")

    assert str(raised.value) == (
        'The "HS256" algorithm cannot sign a "private_key_jwt" client assertion. '
        'Use one of "RS256", "RS384", "RS512", "ES256", "ES384", "ES512", '
        '"PS256", "PS384", "PS512".'
    )


def test_a_key_of_the_wrong_type_is_refused() -> None:
    shared_secret = ECKey.generate_key("P-256")

    with pytest.raises(InvalidArgumentError) as raised:
        _ = PrivateKeyJwt(shared_secret, algorithm="RS256")

    assert str(raised.value) == (
        'The "RS256" algorithm signs with a key of the "RSA" type, '
        'and the given JWK is of the "EC" type.'
    )


def test_a_key_on_the_wrong_curve_is_refused() -> None:
    p_256 = ECKey.generate_key("P-256")

    with pytest.raises(InvalidArgumentError) as raised:
        _ = PrivateKeyJwt(p_256, algorithm="ES384")

    assert str(raised.value) == (
        'The "ES384" algorithm signs with a key on the "P-384" curve '
        '(RFC 7518, Section 3.4), and the given JWK is on the "P-256" curve.'
    )


def test_a_public_key_is_refused() -> None:
    private_key = _private_key()
    public_key = RSAKey.import_key(private_key.as_dict(private=False))

    with pytest.raises(InvalidArgumentError) as raised:
        _ = PrivateKeyJwt(public_key)

    assert str(raised.value) == (
        'The "private_key_jwt" client assertion must be signed with the private '
        'key of the client, and the given JWK has no "d" parameter: it is the '
        "public key. Register that public key at the provider, and sign with "
        "the private one."
    )


def test_the_assertion_is_signed_by_the_private_key() -> None:
    key = _private_key()
    assertion = PrivateKeyJwt(key, clock=MockClock(datetime.fromtimestamp(NOW, UTC)))

    prepared = assertion.authenticate("my-client", "https://issuer.example/token", {})

    body = cast("dict[str, object]", prepared["body"])
    token = body["client_assertion"]
    assert isinstance(token, str)
    decoded = jwt.decode(token, key)
    assert decoded.header["alg"] == "RS256"
    assert decoded.claims["iss"] == "my-client"
    assert decoded.claims["aud"] == "https://issuer.example/token"


def test_the_method_is_private_key_jwt() -> None:
    assert PrivateKeyJwt(_private_key()).get_method() == "private_key_jwt"
