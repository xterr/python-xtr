"""The jwt-bearer assertion base every signed client authentication builds on."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast, final

import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey
from typing_extensions import override
from xtr_clock import MockClock
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.oauth2.client_authentication.abstract_client_assertion import (
    AbstractClientAssertion,
)

if TYPE_CHECKING:
    from joserfc.jwt import Token

NOW = 1_000_000
CLIENT_ID = "my-client"
TOKEN_ENDPOINT = "https://issuer.example/token"  # noqa: S105 -- a test URL, not a credential
ISSUER = "https://issuer.example"


def _clock_at(moment: int) -> MockClock:
    """Freeze a clock at the Unix timestamp ``moment`` names."""
    return MockClock(datetime.fromtimestamp(moment, UTC))


def _key() -> RSAKey:
    """Generate an RSA key carrying a ``kid``."""
    return RSAKey.generate_key(2048, parameters={"kid": "k1"})


@final
class _Assertion(AbstractClientAssertion):
    """A concrete assertion method, for the base's own behaviour."""

    @override
    def get_method(self) -> str:
        return "test_assertion"


def _assertion(
    key: RSAKey | None = None,
    *,
    lifetime: int = 60,
    now: int = NOW,
    issuer: str | None = None,
) -> _Assertion:
    """Build an assertion over ``key``, frozen at ``now``."""
    return _Assertion(key or _key(), "RS256", lifetime, _clock_at(now), issuer)


def _minted(assertion: AbstractClientAssertion, key: RSAKey) -> Token:
    """Authenticate once and return the assertion it built, decoded."""
    prepared = assertion.authenticate(CLIENT_ID, TOKEN_ENDPOINT, {})
    body = cast("dict[str, object]", prepared["body"])
    token = body["client_assertion"]
    assert isinstance(token, str)
    return jwt.decode(token, key)


def test_a_non_positive_lifetime_is_refused() -> None:
    for lifetime in (0, -60):
        with pytest.raises(InvalidArgumentError) as raised:
            _ = _assertion(lifetime=lifetime)

        assert str(raised.value) == (
            "The lifetime of an OAuth2 client assertion must be a positive number "
            f"of seconds, {lifetime} given."
        )


def test_the_assertion_type_names_the_jwt_bearer_format() -> None:
    key = _key()
    assertion = _assertion(key)
    options: dict[str, object] = {"body": {"client_id": CLIENT_ID}}

    prepared = assertion.authenticate(CLIENT_ID, TOKEN_ENDPOINT, options)

    body = cast("dict[str, object]", prepared["body"])
    assert body["client_assertion_type"] == "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
    assert body["client_id"] == CLIENT_ID
    assert isinstance(body["client_assertion"], str)


def test_a_missing_body_is_created_for_the_assertion() -> None:
    prepared = _assertion().authenticate(CLIENT_ID, TOKEN_ENDPOINT, {})

    body = cast("dict[str, object]", prepared["body"])
    assert "client_assertion" in body


def test_the_client_is_both_the_issuer_and_the_subject() -> None:
    key = _key()

    claims = _minted(_assertion(key), key).claims

    assert claims["iss"] == CLIENT_ID
    assert claims["sub"] == CLIENT_ID


def test_the_audience_is_the_token_endpoint_without_an_issuer() -> None:
    key = _key()

    decoded = _minted(_assertion(key), key)

    assert decoded.claims["aud"] == TOKEN_ENDPOINT
    assert decoded.header.get("typ") is None


def test_the_audience_is_the_issuer_when_one_is_given() -> None:
    key = _key()

    decoded = _minted(_assertion(key, issuer=ISSUER), key)

    assert decoded.claims["aud"] == ISSUER
    assert decoded.header["typ"] == "client-authentication+jwt"


def test_the_assertion_is_dated_by_the_clock_and_lives_the_lifetime() -> None:
    key = _key()

    claims = _minted(_assertion(key, lifetime=120), key).claims

    assert claims["iat"] == NOW
    assert claims["exp"] == NOW + 120


def test_the_assertion_carries_a_single_use_identifier() -> None:
    key = _key()
    assertion = _assertion(key)

    first = cast("object", _minted(assertion, key).claims["jti"])
    second = cast("object", _minted(assertion, key).claims["jti"])

    assert isinstance(first, str)
    assert len(first) == 32
    assert first != second


def test_the_header_names_the_algorithm_and_the_key() -> None:
    key = _key()

    header = _minted(_assertion(key), key).header

    assert header["alg"] == "RS256"
    assert header["kid"] == "k1"


def test_create_algorithm_refuses_a_name_outside_the_allow_list() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = AbstractClientAssertion.create_algorithm(
            "HS256",
            {"RS256": "RSA", "ES256": "EC"},
            "private_key_jwt",
        )

    assert str(raised.value) == (
        'The "HS256" algorithm cannot sign a "private_key_jwt" client assertion. '
        'Use one of "RS256", "ES256".'
    )


def test_create_algorithm_resolves_a_name_inside_the_allow_list() -> None:
    assert (
        AbstractClientAssertion.create_algorithm(
            "ES256",
            {"RS256": "RSA", "ES256": "EC"},
            "private_key_jwt",
        )
        == "ES256"
    )
