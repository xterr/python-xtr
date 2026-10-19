"""The OIDC token generator signs an at+jwt access token."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey
from xtr_clock import MockClock
from xtr_security_core.exception import InvalidArgumentError

from tests.support.oidc import NOW, make_key, make_key_set
from xtr_security_http.access_token.oidc import OidcTokenGenerator

if TYPE_CHECKING:
    from joserfc.jwk import KeySet

_ISSUER = "https://issuer.example"
_AUDIENCE = "shop-api"


def _clock_at(moment: int) -> MockClock:
    """Freeze a clock at the Unix timestamp ``moment`` names."""
    return MockClock(datetime.fromtimestamp(moment, UTC))


def _generator(  # noqa: PLR0913 -- a test builder; every knob defaults
    key: RSAKey,
    *,
    algorithms: tuple[str, ...] = ("RS256",),
    audience: str | tuple[str, ...] = _AUDIENCE,
    issuers: tuple[str, ...] = (_ISSUER,),
    claim: str = "sub",
    now: int = NOW,
) -> OidcTokenGenerator:
    """A generator over ``key``, frozen at ``now``, minting what the knobs name."""
    return OidcTokenGenerator(
        algorithms,
        make_key_set(key),
        audience,
        issuers,
        claim,
        _clock_at(now),
    )


def test_an_empty_audience_list_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _generator(make_key(), audience=())


def test_an_audience_that_is_not_a_non_empty_string_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _generator(make_key(), audience=("shop-api", ""))


def test_a_generated_token_is_an_at_jwt_signed_by_the_key() -> None:
    key = make_key()
    generator = _generator(key)

    token = generator.generate("alice")

    decoded = jwt.decode(token, make_key_set(key))
    assert decoded.header == {"alg": "RS256", "typ": "at+jwt"}
    assert decoded.claims == {
        "sub": "alice",
        "iat": NOW,
        "aud": _AUDIENCE,
        "iss": _ISSUER,
    }


def test_a_single_audience_is_kept_as_a_string_and_several_as_a_list() -> None:
    key = make_key()
    single = _generator(key)
    several = _generator(key, audience=(_AUDIENCE, "admin-api"))

    single_claims = jwt.decode(single.generate("alice"), make_key_set(key)).claims
    several_claims = jwt.decode(several.generate("alice"), make_key_set(key)).claims

    assert single_claims["aud"] == _AUDIENCE
    assert several_claims["aud"] == [_AUDIENCE, "admin-api"]


def test_the_claim_naming_the_user_is_configurable() -> None:
    key = make_key()
    generator = _generator(key, claim="email")

    claims = jwt.decode(generator.generate("alice@example.com"), make_key_set(key)).claims

    assert claims["email"] == "alice@example.com"
    assert "sub" not in claims


def test_a_ttl_adds_an_exp_this_many_seconds_after_issuance() -> None:
    key = make_key()
    generator = _generator(key)

    claims = jwt.decode(generator.generate("alice", ttl=3600), make_key_set(key)).claims

    assert claims["exp"] == NOW + 3600


def test_a_zero_ttl_mints_a_token_that_does_not_expire() -> None:
    key = make_key()
    generator = _generator(key)

    claims = jwt.decode(generator.generate("alice", ttl=0), make_key_set(key)).claims

    assert "exp" not in claims


def test_a_negative_ttl_is_refused() -> None:
    generator = _generator(make_key())

    with pytest.raises(InvalidArgumentError) as raised:
        _ = generator.generate("alice", ttl=-1)

    assert str(raised.value) == "Time to live must be a positive integer."


def test_a_not_before_adds_an_nbf_at_the_moment_it_names() -> None:
    key = make_key()
    generator = _generator(key)
    not_before = datetime.fromtimestamp(NOW + 60, UTC)

    claims = jwt.decode(
        generator.generate("alice", not_before=not_before), make_key_set(key)
    ).claims

    assert claims["nbf"] == NOW + 60


def test_the_issued_at_reads_the_clock() -> None:
    key = make_key()
    generator = _generator(key, now=NOW + 123)

    claims = jwt.decode(generator.generate("alice"), make_key_set(key)).claims

    assert claims["iat"] == NOW + 123


def test_the_only_declared_algorithm_is_used_when_none_is_named() -> None:
    key = make_key()
    generator = _generator(key, algorithms=("RS256",))

    token = generator.generate("alice")

    assert jwt.decode(token, make_key_set(key)).header["alg"] == "RS256"


def test_a_named_algorithm_outside_the_declared_ones_is_refused() -> None:
    generator = _generator(make_key(), algorithms=("RS256", "RS512"))

    with pytest.raises(InvalidArgumentError) as raised:
        _ = generator.generate("alice", algorithm="ES256")

    assert str(raised.value) == (
        '"ES256" is not a valid algorithm. Available algorithms: "RS256", "RS512".'
    )


def test_a_named_algorithm_of_the_declared_ones_is_used() -> None:
    key = make_key()
    generator = _generator(key, algorithms=("RS256", "RS512"))

    token = generator.generate("alice", algorithm="RS512")

    assert jwt.decode(token, make_key_set(key), algorithms=["RS512"]).header["alg"] == "RS512"


def test_several_declared_algorithms_without_a_named_one_are_refused() -> None:
    generator = _generator(make_key(), algorithms=("RS256", "RS512"))

    with pytest.raises(InvalidArgumentError) as raised:
        _ = generator.generate("alice")

    assert str(raised.value) == (
        'Please choose an algorithm. Available algorithms: "RS256", "RS512".'
    )


def test_no_declared_algorithm_without_a_named_one_is_refused() -> None:
    generator = _generator(make_key(), algorithms=())

    with pytest.raises(InvalidArgumentError) as raised:
        _ = generator.generate("alice")

    assert str(raised.value) == 'Please choose an algorithm. Available algorithms: "".'


def test_a_given_issuer_outside_the_declared_ones_is_refused() -> None:
    generator = _generator(make_key(), issuers=(_ISSUER, "https://other.example"))

    with pytest.raises(InvalidArgumentError) as raised:
        _ = generator.generate("alice", issuer="https://evil.example")

    assert str(raised.value) == (
        '"https://evil.example" is not a valid issuer. '
        'Available issuers: "https://issuer.example", "https://other.example".'
    )


def test_a_given_issuer_of_the_declared_ones_is_used() -> None:
    key = make_key()
    generator = _generator(key, issuers=(_ISSUER, "https://other.example"))

    claims = jwt.decode(
        generator.generate("alice", issuer="https://other.example"),
        make_key_set(key),
    ).claims

    assert claims["iss"] == "https://other.example"


def test_several_declared_issuers_without_a_given_one_are_refused() -> None:
    generator = _generator(make_key(), issuers=(_ISSUER, "https://other.example"))

    with pytest.raises(InvalidArgumentError) as raised:
        _ = generator.generate("alice")

    assert str(raised.value) == (
        "Please choose an issuer. "
        'Available issuers: "https://issuer.example", "https://other.example".'
    )


def test_a_key_set_holding_no_signing_key_for_the_algorithm_is_refused() -> None:
    encryption_only = RSAKey.generate_key(2048, parameters={"kid": "enc", "use": "enc"})
    generator_with_encryption_key = OidcTokenGenerator(
        ("RS256",),
        make_key_set(encryption_only),
        _AUDIENCE,
        (_ISSUER,),
        clock=_clock_at(NOW),
    )
    generator_with_wrong_kty = OidcTokenGenerator(
        ("HS256",),
        make_key_set(make_key()),
        _AUDIENCE,
        (_ISSUER,),
        clock=_clock_at(NOW),
    )

    with pytest.raises(InvalidArgumentError) as encryption_raised:
        _ = generator_with_encryption_key.generate("alice")
    assert str(encryption_raised.value) == 'No JWK found to sign with the "RS256" algorithm.'

    with pytest.raises(InvalidArgumentError) as kty_raised:
        _ = generator_with_wrong_kty.generate("alice")
    assert str(kty_raised.value) == 'No JWK found to sign with the "HS256" algorithm.'


def test_the_signing_key_is_selected_from_the_key_set_by_use() -> None:
    signing = RSAKey.generate_key(2048, parameters={"kid": "signing", "use": "sig"})
    encryption_only = RSAKey.generate_key(2048, parameters={"kid": "enc", "use": "enc"})
    generator = OidcTokenGenerator(
        ("RS256",),
        make_key_set(signing, encryption_only),
        _AUDIENCE,
        (_ISSUER,),
        clock=_clock_at(NOW),
    )

    token = generator.generate("alice")

    assert jwt.decode(token, make_key_set(signing)).claims["sub"] == "alice"
    with pytest.raises(Exception):  # noqa: B017, PT011 -- any JOSE refusal: the other key did not sign it
        _ = jwt.decode(token, make_key_set(encryption_only))


def test_a_key_declaring_no_use_is_selected() -> None:
    keyset: KeySet = make_key_set(make_key("unlabelled"))
    generator = OidcTokenGenerator(
        ("RS256",),
        keyset,
        _AUDIENCE,
        (_ISSUER,),
        clock=_clock_at(NOW),
    )

    token = generator.generate("alice")

    assert jwt.decode(token, keyset).claims["sub"] == "alice"
