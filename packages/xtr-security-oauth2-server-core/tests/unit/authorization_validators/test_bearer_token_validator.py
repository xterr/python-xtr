"""Reading the bearer token off a request, and refusing every way it can fail."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final

import pytest

from tests.support.messages import server_request
from tests.support.repositories import InMemoryAccessTokenRepository
from tests.support.signing import FROZEN_NOW, ISSUER, KEY_ID, make_clock, make_signer
from xtr_security_oauth2_server_core.authorization_validators import (
    AuthorizationValidatorInterface,
    BearerTokenValidatorInterface,
)
from xtr_security_oauth2_server_core.authorization_validators.bearer_token_validator import (
    BearerTokenValidator,
)
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface

_NOW: Final[int] = int(FROZEN_NOW.timestamp())
_AN_HOUR: Final[int] = 3600

_CLAIMS: Final[Mapping[str, object]] = {
    "iss": ISSUER,
    "sub": "user-1",
    "aud": "client-1",
    "client_id": "client-1",
    "iat": _NOW,
    "nbf": _NOW,
    "exp": _NOW + _AN_HOUR,
    "jti": "access-1",
    "scope": "read write",
}

_HEADER: Final[Mapping[str, object]] = {"typ": "at+jwt", "kid": KEY_ID}


def _signed(
    claims: Mapping[str, object] | None = None,
    header: Mapping[str, object] | None = None,
) -> str:
    provider = make_signer().jws_provider

    return provider.create(
        {**_CLAIMS, **(claims if claims is not None else {})},
        _HEADER if header is None else header,
    ).get_token()


def _request(authorization: str | None = None) -> ServerRequestInterface:
    headers = {} if authorization is None else {"Authorization": authorization}

    return server_request("GET", "https://api.example.com/me", headers=headers)


def _validator(
    tokens: InMemoryAccessTokenRepository | None = None,
    audience: str | None = None,
    leeway: timedelta | None = None,
) -> BearerTokenValidator:
    return BearerTokenValidator(
        tokens if tokens is not None else InMemoryAccessTokenRepository(),
        make_signer().jws_provider,
        ISSUER,
        make_clock(),
        audience,
        leeway,
    )


def test_it_declares_both_contracts_it_answers() -> None:
    # Declared, not merely satisfied: a runtime-checkable contract answers
    # issubclass() structurally, so only its place in the order the class
    # resolves against proves the base is still there.
    assert AuthorizationValidatorInterface in BearerTokenValidator.__mro__
    assert BearerTokenValidatorInterface in BearerTokenValidator.__mro__


@pytest.mark.anyio
async def test_a_request_without_an_authorization_header_is_refused() -> None:
    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request())

    assert refusal.value.get_error_type() == "access_denied"
    assert "Authorization" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_token_handed_over_without_a_header_is_judged_the_same_way() -> None:
    claims = await _validator().validate_bearer_token(_request(), _signed())

    assert claims["jti"] == "access-1"
    assert claims["client_id"] == "client-1"
    assert claims["scope"] == "read write"


@pytest.mark.anyio
async def test_a_token_handed_over_that_was_revoked_is_refused() -> None:
    tokens = InMemoryAccessTokenRepository()
    await tokens.revoke_access_token("access-1")

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator(tokens).validate_bearer_token(_request(), _signed())

    assert refusal.value.get_hint() == "Access token has been revoked"


@pytest.mark.anyio
async def test_a_token_handed_over_that_is_not_a_token_is_refused() -> None:
    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_bearer_token(_request(), "not-a-token")

    assert refusal.value.get_error_type() == "access_denied"


@pytest.mark.anyio
async def test_a_header_of_another_scheme_carries_no_bearer_token() -> None:
    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request("Basic abc"))

    assert "Bearer" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_the_scheme_is_read_however_it_is_cased() -> None:
    annotated = await _validator().validate_authorization(_request(f"bearer {_signed()}"))

    assert annotated.get_attribute("oauth_access_token_id") == "access-1"


@pytest.mark.anyio
async def test_a_header_naming_the_scheme_and_nothing_else_is_refused() -> None:
    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request("Bearer   "))

    assert "Bearer" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_something_that_is_not_a_token_at_all_is_refused() -> None:
    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request("Bearer not-a-token"))

    assert refusal.value.get_error_type() == "access_denied"


@pytest.mark.anyio
async def test_a_token_whose_signature_was_tampered_with_is_refused() -> None:
    head, payload, signature = _signed().split(".")
    flipped = "A" if signature[5] != "A" else "B"
    tampered = f"{head}.{payload}.{signature[:5]}{flipped}{signature[6:]}"

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {tampered}"))

    assert "verified" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_token_whose_header_says_nothing_about_its_type_is_refused() -> None:
    token = _signed(header={"kid": KEY_ID})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert "at+jwt" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_an_identity_token_presented_as_an_access_token_is_refused() -> None:
    token = _signed(header={"typ": "JWT", "kid": KEY_ID})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert "at+jwt" in str(refusal.value.get_hint())


@pytest.mark.anyio
@pytest.mark.parametrize(
    "declared",
    ["at+jwt", "application/at+jwt", "AT+JWT", "Application/AT+JWT", " at+jwt "],
)
async def test_the_media_type_of_the_profile_is_read_however_it_was_written(
    declared: str,
) -> None:
    # "The resource server MUST verify that the "typ" header value is "at+jwt"
    # or "application/at+jwt"" (RFC 9068 section 4) — the two spellings of one
    # media type, which RFC 7515 section 4.1.9 has a reader treat alike and
    # compare without regard to case.
    token = _signed(header={"typ": declared, "kid": KEY_ID})

    annotated = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert annotated.get_attribute("oauth_access_token_id") == "access-1"


@pytest.mark.anyio
@pytest.mark.parametrize("declared", ["jwt", "application/jwt", "at+jwt;v=1", "atjwt"])
async def test_another_media_type_is_refused_however_it_was_written(declared: str) -> None:
    # The other half of the same sentence: a token carrying any other value is
    # rejected, and neither prefixing nor casing makes one of these the
    # profile's.
    token = _signed(header={"typ": declared, "kid": KEY_ID})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert "at+jwt" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_token_carrying_no_expiry_is_refused() -> None:
    token = _signed({"exp": "soon"})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert "expired" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_an_expired_token_is_refused() -> None:
    token = _signed({"exp": _NOW - 1})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert "expired" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_leeway_admits_a_token_that_has_only_just_expired() -> None:
    token = _signed({"exp": _NOW - 10})
    validator = _validator(leeway=timedelta(seconds=30))

    annotated = await validator.validate_authorization(_request(f"Bearer {token}"))

    assert annotated.get_attribute("oauth_access_token_id") == "access-1"


@pytest.mark.anyio
async def test_a_token_that_is_not_usable_yet_is_refused() -> None:
    token = _signed({"nbf": _NOW + 60})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert "not" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_leeway_admits_a_token_usable_a_moment_from_now() -> None:
    token = _signed({"nbf": _NOW + 10})
    validator = _validator(leeway=timedelta(seconds=30))

    annotated = await validator.validate_authorization(_request(f"Bearer {token}"))

    assert annotated.get_attribute("oauth_access_token_id") == "access-1"


@pytest.mark.anyio
async def test_a_token_from_another_authorization_server_is_refused() -> None:
    token = _signed({"iss": "https://other.example.com"})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert "issuer" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_token_addressed_elsewhere_is_refused_when_an_audience_is_configured() -> None:
    token = _signed({"aud": "another-api"})
    validator = _validator(audience="https://api.example.com")

    with pytest.raises(OAuthServerError) as refusal:
        _ = await validator.validate_authorization(_request(f"Bearer {token}"))

    assert "audience" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_token_addressed_to_the_one_audience_is_accepted() -> None:
    token = _signed({"aud": "https://api.example.com"})
    validator = _validator(audience="https://api.example.com")

    annotated = await validator.validate_authorization(_request(f"Bearer {token}"))

    assert annotated.get_attribute("oauth_access_token_id") == "access-1"


@pytest.mark.anyio
async def test_a_token_addressed_to_several_audiences_is_accepted() -> None:
    token = _signed({"aud": ["another-api", "https://api.example.com"]})
    validator = _validator(audience="https://api.example.com")

    annotated = await validator.validate_authorization(_request(f"Bearer {token}"))

    assert annotated.get_attribute("oauth_access_token_id") == "access-1"


@pytest.mark.anyio
async def test_with_no_audience_configured_the_one_the_token_names_is_not_judged() -> None:
    token = _signed({"aud": "whoever"})

    annotated = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert annotated.get_attribute("oauth_access_token_id") == "access-1"


@pytest.mark.anyio
async def test_a_revoked_token_is_refused() -> None:
    tokens = InMemoryAccessTokenRepository()
    await tokens.revoke_access_token("access-1")

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator(tokens).validate_authorization(_request(f"Bearer {_signed()}"))

    assert "revoked" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_an_accepted_token_annotates_the_request_with_what_it_says() -> None:
    annotated = await _validator().validate_authorization(_request(f"Bearer {_signed()}"))

    assert annotated.get_attribute("oauth_access_token_id") == "access-1"
    assert annotated.get_attribute("oauth_client_id") == "client-1"
    assert annotated.get_attribute("oauth_user_id") == "user-1"
    assert annotated.get_attribute("oauth_scopes") == ["read", "write"]


@pytest.mark.anyio
async def test_a_token_carrying_no_scope_annotates_an_empty_list() -> None:
    token = _signed({"scope": ""})

    annotated = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert annotated.get_attribute("oauth_scopes") == []


@pytest.mark.anyio
async def test_a_token_naming_no_resource_owner_annotates_none() -> None:
    token = _signed({"sub": "client-1"})

    annotated = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert annotated.get_attribute("oauth_user_id") == "client-1"


@pytest.mark.anyio
async def test_a_token_whose_identifier_is_not_a_name_is_refused() -> None:
    token = _signed({"jti": 7})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert refusal.value.get_error_type() == "access_denied"


def test_its_reading_names_no_token_and_no_key() -> None:
    shown = repr(_validator())

    assert "BearerTokenValidator" in shown
    assert ISSUER in shown
