"""The ID token reader decodes without verifying, and validates the claims."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey
from xtr_clock import MockClock
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.oidc.oidc_id_token import OidcIdToken

_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)
_ISSUER = "https://issuer.example"
_AUDIENCE = "client-1"


def _key() -> RSAKey:
    """A fresh RSA signing key."""
    return RSAKey.generate_key(2048, parameters={"kid": "k1"})


def _token(key: RSAKey, claims: dict[str, object]) -> str:
    """A signed JWT carrying ``claims`` — the signature is not the subject here."""
    return jwt.encode({"alg": "RS256", "kid": key.kid}, claims, key)


def _claims(**extra: object) -> dict[str, object]:
    """A valid claim set for the frozen clock, plus ``extra``."""
    return {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": "alice",
        "iat": _NOW,
        "exp": _NOW + 3600,
        **extra,
    }


def _reader(drift: int = 0) -> OidcIdToken:
    """A reader frozen at the test instant, allowing ``drift`` seconds."""
    return OidcIdToken(MockClock(_FROZEN), drift)


@pytest.mark.anyio
async def test_it_decodes_the_claims_without_verifying_the_signature() -> None:
    key = _key()
    token = _token(key, _claims())

    assert await _reader().decode(token) == _claims()


@pytest.mark.anyio
async def test_a_malformed_token_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = await _reader().decode("not-a-jwt")

    assert str(raised.value) == "Invalid ID token format."


@pytest.mark.anyio
async def test_a_payload_that_is_not_json_is_refused() -> None:
    from joserfc import jws  # noqa: PLC0415 -- test-local helpers

    key = _key()
    unsigned = jws.serialize_compact({"alg": "RS256"}, b"not json", key)

    with pytest.raises(AuthenticationError):
        _ = await _reader().decode(unsigned)


@pytest.mark.anyio
async def test_a_payload_that_is_not_an_object_is_refused() -> None:
    from joserfc import jws  # noqa: PLC0415 -- test-local helpers

    key = _key()
    list_payload = jws.serialize_compact({"alg": "RS256"}, b"[1, 2, 3]", key)

    with pytest.raises(AuthenticationError):
        _ = await _reader().decode(list_payload)


@pytest.mark.anyio
async def test_a_missing_mandatory_claim_is_refused() -> None:
    for claim in ("iss", "aud", "exp", "iat", "sub"):
        claims = _claims()
        del claims[claim]

        with pytest.raises(AuthenticationError) as raised:
            _reader().validate_claims(claims, _ISSUER, _AUDIENCE)

        assert claim in str(raised.value)


def test_a_wrong_issuer_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _reader().validate_claims(_claims(iss="https://evil.example"), _ISSUER, _AUDIENCE)

    assert "does not match the expected" in str(raised.value)


def test_a_wrong_audience_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        _reader().validate_claims(_claims(aud="another-client"), _ISSUER, _AUDIENCE)


def test_an_audience_list_naming_the_client_is_accepted() -> None:
    _reader().validate_claims(_claims(aud=["other-api", _AUDIENCE]), _ISSUER, _AUDIENCE)


def test_an_audience_list_without_the_client_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        _reader().validate_claims(_claims(aud=["other-api"]), _ISSUER, _AUDIENCE)


def test_an_expired_token_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        _reader().validate_claims(_claims(exp=_NOW - 1), _ISSUER, _AUDIENCE)


def test_the_drift_admits_a_just_expired_token() -> None:
    _reader(drift=30).validate_claims(_claims(exp=_NOW - 30), _ISSUER, _AUDIENCE)


def test_a_token_issued_in_the_future_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        _reader().validate_claims(_claims(iat=_NOW + 60), _ISSUER, _AUDIENCE)


def test_a_token_not_yet_valid_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        _reader().validate_claims(_claims(nbf=_NOW + 60), _ISSUER, _AUDIENCE)


def test_a_non_timestamp_exp_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        _reader().validate_claims(_claims(exp="soon"), _ISSUER, _AUDIENCE)


def test_a_non_timestamp_iat_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _reader().validate_claims(_claims(iat="just now"), _ISSUER, _AUDIENCE)

    assert '"iat" claim is not a timestamp' in str(raised.value)


def test_an_audience_of_an_unusable_shape_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        _reader().validate_claims(_claims(aud=7), _ISSUER, _AUDIENCE)


def test_an_empty_subject_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _reader().validate_claims(_claims(sub=""), _ISSUER, _AUDIENCE)

    assert '"sub" claim must be a non-empty string' in str(raised.value)


def test_a_matching_azp_is_accepted() -> None:
    _reader().validate_claims(_claims(azp=_AUDIENCE), _ISSUER, _AUDIENCE)


def test_a_wrong_azp_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _reader().validate_claims(_claims(azp="another-client"), _ISSUER, _AUDIENCE)

    assert "azp" in str(raised.value)


def test_a_matching_nonce_is_accepted() -> None:
    _reader().validate_claims(_claims(nonce="the-nonce"), _ISSUER, _AUDIENCE, "the-nonce")


def test_a_missing_nonce_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        _reader().validate_claims(_claims(), _ISSUER, _AUDIENCE, "the-nonce")


def test_a_wrong_nonce_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        _reader().validate_claims(_claims(nonce="other"), _ISSUER, _AUDIENCE, "the-nonce")


def test_no_max_age_leaves_auth_time_unchecked() -> None:
    _reader().validate_claims(_claims(), _ISSUER, _AUDIENCE)


def test_a_max_age_without_auth_time_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _reader().validate_claims(_claims(), _ISSUER, _AUDIENCE, max_age=300)

    assert "auth_time" in str(raised.value)


def test_a_recent_auth_time_satisfies_the_max_age() -> None:
    _reader().validate_claims(_claims(auth_time=_NOW - 60), _ISSUER, _AUDIENCE, max_age=300)


def test_an_old_auth_time_exceeds_the_max_age() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _reader().validate_claims(_claims(auth_time=_NOW - 400), _ISSUER, _AUDIENCE, max_age=300)

    assert "max_age" in str(raised.value)


def test_the_drift_admits_an_older_auth_time() -> None:
    _reader(drift=120).validate_claims(
        _claims(auth_time=_NOW - 400),
        _ISSUER,
        _AUDIENCE,
        max_age=300,
    )
