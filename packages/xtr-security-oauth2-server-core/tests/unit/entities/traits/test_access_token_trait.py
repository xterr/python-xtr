"""An access token signs itself into the JWT a resource server reads.

Every assertion here decodes what the entity produced with the very key that
signed it, so what is checked is the token on the wire rather than a call
somebody expected to be made.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, final

import pytest
from joserfc import jwt as joserfc_jwt
from xtr_security_jwt.services.jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.key_loader import RawKeyLoader, generate_signing_key
from xtr_security_jwt.signature.created_jws import CreatedJws

from tests.support.entities import AccessToken, make_client, make_scope, make_scopes
from tests.support.signing import ALGORITHM, ISSUER, KEY_ID, SIGNING_KEY, make_clock, make_signer
from xtr_security_oauth2_server_core.entities.access_token_signer import AccessTokenSigner
from xtr_security_oauth2_server_core.entities.traits.access_token_trait import RESERVED_CLAIMS
from xtr_security_oauth2_server_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_clock import ClockInterface
    from xtr_security_jwt.signature.loaded_jws import LoadedJws

_IDENTIFIER = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
_ISSUED_AT = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
_EXPIRES_AT = _ISSUED_AT + timedelta(hours=1)

#: An ECDSA algorithm, whose every signature over the same input differs: two
#: equal strings from it can only be one signing read twice.
_RANDOMISED_ALGORITHM = "ES256"
_RANDOMISED_KEY_LOADER = RawKeyLoader(
    generate_signing_key(_RANDOMISED_ALGORITHM).as_pem(private=True).decode("utf-8"),
    None,
)


def _randomised_signer(clock: ClockInterface) -> AccessTokenSigner:
    """Return a signer whose signatures are never the same twice."""
    return AccessTokenSigner(
        jws_provider=JoserfcJwsProvider(
            _RANDOMISED_KEY_LOADER,
            _RANDOMISED_ALGORITHM,
            None,
            0,
            clock,
        ),
        key_id=KEY_ID,
        issuer=ISSUER,
        clock=clock,
    )


@final
class _UnsignedProvider:
    """A provider that hands back a token it did not sign."""

    def create(
        self,
        payload: Mapping[str, object],
        header: Mapping[str, object] | None = None,
    ) -> CreatedJws:
        del payload, header
        return CreatedJws("unsigned.token.", is_signed=False)

    def load(self, token: str) -> LoadedJws:  # pragma: no cover -- never read here
        del token
        raise NotImplementedError


def _access_token(
    signer: AccessTokenSigner | None = None,
    *,
    user_identifier: str | None = "user-1",
) -> AccessToken:
    """Return a token ready to sign itself, built the way a grant builds one."""
    token = AccessToken()
    token.set_identifier(_IDENTIFIER)
    token.set_client(make_client())
    token.set_expiry_date_time(_EXPIRES_AT)
    for scope in make_scopes("read", "write"):
        token.add_scope(scope)
    if user_identifier is not None:
        token.set_user_identifier(user_identifier)
    token.set_private_key(signer if signer is not None else make_signer())
    return token


def _decoded(token: AccessToken) -> joserfc_jwt.Token:
    """Sign ``token`` and read it back with the key that signed it."""
    return joserfc_jwt.decode(token.to_string(), SIGNING_KEY, algorithms=[ALGORITHM])


def test_the_header_names_the_access_token_profile_the_key_and_the_algorithm() -> None:
    assert _decoded(_access_token()).header == {
        "typ": "at+jwt",
        "kid": KEY_ID,
        "alg": ALGORITHM,
    }


def test_the_claims_are_exactly_the_ones_the_profile_asks_for() -> None:
    issued_at = int(_ISSUED_AT.timestamp())

    assert _decoded(_access_token()).claims == {
        "iss": ISSUER,
        "sub": "user-1",
        "aud": "client-1",
        "client_id": "client-1",
        "iat": issued_at,
        "nbf": issued_at,
        "exp": int(_EXPIRES_AT.timestamp()),
        "jti": _IDENTIFIER,
        "scope": "read write",
    }


def test_the_subject_falls_back_to_the_client_when_no_user_is_named() -> None:
    claims = _decoded(_access_token(user_identifier=None)).claims

    assert claims["sub"] == "client-1"


def test_the_audience_is_the_configured_one_when_there_is_one() -> None:
    claims = _decoded(_access_token(make_signer("https://api.example.com"))).claims

    assert claims["aud"] == "https://api.example.com"


def test_the_scope_claim_is_empty_when_the_token_carries_no_scope() -> None:
    token = AccessToken()
    token.set_identifier(_IDENTIFIER)
    token.set_client(make_client())
    token.set_expiry_date_time(_EXPIRES_AT)
    token.set_private_key(make_signer())

    assert _decoded(token).claims["scope"] == ""


def test_the_times_are_read_from_the_clock_the_signer_carries() -> None:
    later = _ISSUED_AT + timedelta(minutes=30)
    claims = _decoded(_access_token(make_signer(clock=make_clock(later)))).claims

    assert claims["iat"] == int(later.timestamp())
    assert claims["nbf"] == int(later.timestamp())


def test_extra_claims_are_signed_in_beside_the_profile_ones() -> None:
    token = _access_token()
    token.set_extra_claims({"tenant": "acme", "tier": 3})

    claims = _decoded(token).claims

    assert claims["tenant"] == "acme"
    assert claims["tier"] == 3


def test_an_extra_claim_taking_a_name_the_token_mints_is_refused() -> None:
    token = _access_token()

    with pytest.raises(InvalidArgumentError, match="iss"):
        token.set_extra_claims({"iss": "https://elsewhere.example.com", "tenant": "acme"})


def test_every_name_the_token_mints_is_reserved() -> None:
    assert sorted(RESERVED_CLAIMS) == [
        "aud",
        "client_id",
        "exp",
        "iat",
        "iss",
        "jti",
        "nbf",
        "scope",
        "sub",
    ]


def test_signing_before_a_signer_was_handed_over_is_refused() -> None:
    token = AccessToken()

    with pytest.raises(InvalidArgumentError, match="no signer"):
        _ = token.to_string()


def test_a_token_the_provider_did_not_sign_is_refused() -> None:
    signer = AccessTokenSigner(
        jws_provider=_UnsignedProvider(),
        key_id=KEY_ID,
        issuer=ISSUER,
        clock=make_clock(),
    )

    with pytest.raises(InvalidArgumentError, match="unsigned"):
        _ = _access_token(signer).to_string()


def test_its_reading_holds_neither_the_signed_token_nor_the_signer() -> None:
    token = _access_token()
    signed = token.to_string()

    reading = repr(token)

    assert signed not in reading
    assert "AccessTokenSigner" not in reading
    assert reading == "AccessToken(identifier='a1b2c3d4...')"


def test_to_string_returns_the_same_string_on_every_call() -> None:
    clock = make_clock()
    token = _access_token(_randomised_signer(clock))
    first = token.to_string()
    clock.sleep(5)

    second = token.to_string()

    assert second == first


_SIGNED_CLAIM_CHANGES: dict[str, Callable[[AccessToken], None]] = {
    "set_identifier": lambda token: token.set_identifier("another-identifier"),
    "set_expiry_date_time": lambda token: token.set_expiry_date_time(
        _EXPIRES_AT + timedelta(hours=1),
    ),
    "set_user_identifier": lambda token: token.set_user_identifier("user-2"),
    "set_client": lambda token: token.set_client(make_client("client-2")),
    "add_scope": lambda token: token.add_scope(make_scope("admin")),
    "set_private_key": lambda token: token.set_private_key(
        make_signer("https://api.example.com"),
    ),
    "set_extra_claims": lambda token: token.set_extra_claims({"tenant": "acme"}),
}


@pytest.mark.parametrize("change", _SIGNED_CLAIM_CHANGES.values(), ids=_SIGNED_CLAIM_CHANGES.keys())
def test_changing_a_signed_claim_signs_again(change: Callable[[AccessToken], None]) -> None:
    # The frozen RS256 signer signs the same claims into the same string, so a
    # different string here is the changed claim, never a fresh signature.
    token = _access_token()
    before = token.to_string()
    change(token)

    after = token.to_string()

    assert after != before
