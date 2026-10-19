"""The claims a logout token must carry, and the ones it must not."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from xtr_clock import MockClock
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.oidc.oidc_logout_token import OidcLogoutToken

_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)
_ISSUER = "https://issuer.example"
_CLIENT = "shop-api"
_OMIT = object()
"""A sentinel standing for a claim the token does not carry at all."""


def _claims(**overrides: object) -> dict[str, object]:
    """A logout token's claims: the mandatory six, a ``sid``, and nothing else."""
    claims: dict[str, object] = {
        "iss": _ISSUER,
        "aud": _CLIENT,
        "iat": _NOW,
        "exp": _NOW + 600,
        "jti": "the-logout",
        "events": {OidcLogoutToken.EVENT: {}},
        "sid": "sid-1",
    }
    claims.update(overrides)
    return {name: value for name, value in claims.items() if value is not _OMIT}


def _token(clock: MockClock | None = None, drift: int = 0) -> OidcLogoutToken:
    return OidcLogoutToken(clock if clock is not None else MockClock(_FROZEN), drift)


def test_a_valid_token_names_the_session_that_ended() -> None:
    assert _token().validate_claims(_claims(), _ISSUER, _CLIENT) == "sid-1"


def test_the_event_member_is_the_backchannel_logout_one() -> None:
    assert OidcLogoutToken.EVENT == "http://schemas.openid.net/event/backchannel-logout"


@pytest.mark.parametrize("claim", ["iss", "aud", "iat", "exp", "jti", "events"])
def test_each_mandatory_claim_is_required(claim: str) -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(**{claim: _OMIT}), _ISSUER, _CLIENT)

    assert f'the mandatory claim(s) "{claim}" are missing' in str(raised.value)


def test_a_subject_is_not_required() -> None:
    assert _token().validate_claims(_claims(), _ISSUER, _CLIENT) == "sid-1"
    assert _token().validate_claims(_claims(sub="alice"), _ISSUER, _CLIENT) == "sid-1"


def test_an_unknown_issuer_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(iss="https://other.example"), _ISSUER, _CLIENT)

    assert "does not match the expected" in str(raised.value)


def test_the_audience_may_name_several_clients() -> None:
    assert _token().validate_claims(_claims(aud=["other", _CLIENT]), _ISSUER, _CLIENT) == "sid-1"


def test_an_audience_not_naming_the_client_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(aud="other-api"), _ISSUER, _CLIENT)

    assert 'the audience does not name "shop-api"' in str(raised.value)


def test_an_audience_that_is_neither_a_string_nor_a_list_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(aud=7), _ISSUER, _CLIENT)

    assert 'the audience does not name "shop-api"' in str(raised.value)


def test_an_expired_token_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(exp=_NOW - 1), _ISSUER, _CLIENT)

    assert "the token has expired" in str(raised.value)


def test_an_expiry_within_the_drift_is_tolerated() -> None:
    assert _token(drift=30).validate_claims(_claims(exp=_NOW - 30), _ISSUER, _CLIENT) == "sid-1"


def test_a_token_issued_in_the_future_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(iat=_NOW + 1), _ISSUER, _CLIENT)

    assert "issued in the future" in str(raised.value)


def test_an_issued_at_within_the_drift_is_tolerated() -> None:
    assert _token(drift=30).validate_claims(_claims(iat=_NOW + 30), _ISSUER, _CLIENT) == "sid-1"


@pytest.mark.parametrize("claim", ["exp", "iat"])
def test_a_time_claim_that_is_no_timestamp_is_refused(*, claim: str) -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(**{claim: "soon"}), _ISSUER, _CLIENT)

    assert f'the "{claim}" claim is not a timestamp' in str(raised.value)


def test_a_boolean_time_claim_is_refused() -> None:
    with pytest.raises(AuthenticationError):
        _ = _token().validate_claims(_claims(exp=True), _ISSUER, _CLIENT)


def test_a_nonce_is_refused() -> None:
    """An ID token replayed as a logout token must fail: only an ID token carries one."""
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(nonce="n-1"), _ISSUER, _CLIENT)

    assert 'it carries a "nonce" claim, which only an ID token does' in str(raised.value)


def test_the_events_claim_must_be_an_object() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(
            _claims(events=["http://schemas.openid.net/event/backchannel-logout"]),
            _ISSUER,
            _CLIENT,
        )

    assert 'the "events" claim must be an object' in str(raised.value)


def test_the_events_claim_must_carry_the_backchannel_logout_member() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(
            _claims(events={"https://other.example/event": {}}),
            _ISSUER,
            _CLIENT,
        )

    assert "must be an object carrying" in str(raised.value)
    assert OidcLogoutToken.EVENT in str(raised.value)


def test_the_backchannel_logout_member_must_be_an_object() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(events={OidcLogoutToken.EVENT: []}), _ISSUER, _CLIENT)

    assert "must be an object carrying" in str(raised.value)
    assert OidcLogoutToken.EVENT in str(raised.value)


def test_a_missing_sid_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(sid=_OMIT), _ISSUER, _CLIENT)

    assert 'the "sid" claim must be a non-empty string' in str(raised.value)


def test_an_empty_sid_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(sid=""), _ISSUER, _CLIENT)

    assert 'the "sid" claim must be a non-empty string' in str(raised.value)


def test_a_non_string_sid_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = _token().validate_claims(_claims(sid=7), _ISSUER, _CLIENT)

    assert 'the "sid" claim must be a non-empty string' in str(raised.value)


def test_a_replayed_jti_is_not_remembered() -> None:
    """``exp`` bounds a captured token; nothing here refuses a replayed ``jti``."""
    token = _token()
    claims = _claims()

    assert token.validate_claims(claims, _ISSUER, _CLIENT) == "sid-1"
    assert token.validate_claims(claims, _ISSUER, _CLIENT) == "sid-1"
