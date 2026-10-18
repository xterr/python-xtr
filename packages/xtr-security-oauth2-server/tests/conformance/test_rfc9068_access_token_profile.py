"""RFC 9068 — JSON Web Token (JWT) Profile for OAuth 2.0 Access Tokens.

Section 2 fixes the header and the claims of an issued token, so those are read
off a token a served deployment issued. Section 4 is what a resource server
owes, so the refusals are driven either through a firewall reading this
server's own tokens or through the reader itself, where a token has to be
hand-made — a token signed with no algorithm at all is not something the
issuing side can be asked to produce.
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Final, cast

import pytest
from fastapi import APIRouter, FastAPI
from xtr_security_oauth2_server_core.authorization_validators.bearer_token_validator import (
    BearerTokenValidator,
)
from xtr_security_oauth2_server_core.entities.traits.access_token_trait import RESERVED_CLAIMS
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

from tests.fixtures.oauth2_audience_app.config import AUDIENCE
from tests.support.messages import server_request
from tests.support.repositories import InMemoryAccessTokenRepository
from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    SEED_PATH,
    claims_of,
    client_credentials_token,
    header_of,
    json_of,
    oauth2_kernel,
    served_application,
    serving,
    text_field,
)
from tests.support.signing import FROZEN_NOW, ISSUER, KEY_ID, make_clock, make_signer

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio

#: The media type section 2.1 registers, written the short way it recommends.
TYPE_HEADER: Final = "at+jwt"

#: The same media type written in full, which section 4 says a reader must
#: accept as well.
FULL_TYPE_HEADER: Final = "application/at+jwt"

_NOW: Final = int(FROZEN_NOW.timestamp())
_AN_HOUR: Final = 3600

#: A well-formed claim set, for the hand-made tokens below.
_CLAIMS: Final[Mapping[str, object]] = {
    "iss": ISSUER,
    "sub": "user-1",
    "aud": "client-1",
    "client_id": "client-1",
    "iat": _NOW,
    "nbf": _NOW,
    "exp": _NOW + _AN_HOUR,
    "jti": "access-1",
    "scope": "read",
}

FIREWALL: Final = "api"


def _api(app: FastAPI) -> None:
    """Mount an API behind the firewall that reads this server's access tokens."""
    router = APIRouter(prefix="/api")

    @router.get("/me")
    async def me() -> dict[str, str]:
        return {"read": "yes"}

    app.include_router(router)


def _application() -> FastAPI:
    """Return a deployment whose tokens are addressed to the client they are for."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_firewall_app"),
        extend=_api,
    )


def _audience_application() -> FastAPI:
    """Return a deployment whose tokens name one resource, and read only those."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_audience_app"),
        extend=_api,
    )


def _validator(audience: str | None = None) -> BearerTokenValidator:
    """Return the reader a resource server uses, over the suite's own key."""
    return BearerTokenValidator(
        InMemoryAccessTokenRepository(),
        make_signer().jws_provider,
        ISSUER,
        make_clock(),
        audience,
        None,
    )


def _request(authorization: str) -> ServerRequestInterface:
    """Return a request presenting ``authorization``."""
    return server_request(
        "GET",
        "https://api.example.com/me",
        headers={"Authorization": authorization},
    )


def _signed(
    claims: Mapping[str, object] | None = None,
    header: Mapping[str, object] | None = None,
) -> str:
    """Return a token this suite's key signed, over the claims given."""
    return (
        make_signer()
        .jws_provider.create(
            {**_CLAIMS, **(claims if claims is not None else {})},
            {"typ": TYPE_HEADER, "kid": KEY_ID} if header is None else header,
        )
        .get_token()
    )


def _unsigned(header: Mapping[str, object], claims: Mapping[str, object]) -> str:
    """Return a compact token whose signature is empty, as ``alg: none`` is written."""

    def segment(payload: Mapping[str, object]) -> str:
        encoded = json.dumps(payload).encode()

        return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")

    return f"{segment(header)}.{segment(claims)}."


async def _issued_token() -> str:
    """Return an access token a served deployment issued to a client for itself."""
    async with serving(_application()) as client:
        return await client_credentials_token(client)


# Section 2.1 — Header


async def test_a_token_is_signed() -> None:
    # "JWT access tokens MUST be signed" (section 2.1): three segments, the
    # third of them not empty.
    token = await _issued_token()
    segments = token.split(".")

    assert len(segments) == 3
    assert segments[2] != ""


async def test_a_token_names_a_real_signing_algorithm() -> None:
    # "JWT access tokens MUST NOT use "none" as the signing algorithm"
    # (section 2.1), and section 2.1 requires RS256 among the supported ones.
    header = header_of(await _issued_token())

    assert header["alg"] == "RS256"


async def test_a_token_declares_the_media_type_of_the_profile() -> None:
    # "JWT access tokens MUST include this media type in the "typ" header
    # parameter to explicitly declare that the JWT represents an access token
    # complying with this profile ... the "typ" value used SHOULD be "at+jwt""
    # (section 2.1).
    assert header_of(await _issued_token())["typ"] == TYPE_HEADER


async def test_a_token_names_the_key_it_was_signed_with() -> None:
    # Section 4 has the reader "use the keys provided by the authorization
    # server", which a ``kid`` matching the published set is what makes
    # possible.
    header = header_of(await _issued_token())
    async with serving(_application()) as client:
        published = json_of(await client.get("/.well-known/jwks.json"))

    keys = published["keys"]
    assert isinstance(keys, list)
    # What a decoded list holds cannot be known from its type, so each key is
    # asked what it is before its id is read.
    named: set[object] = set()
    for key in cast("Sequence[object]", keys):
        if isinstance(key, dict):
            named.add(cast("Mapping[str, object]", key).get("kid"))
    assert header["kid"] in named


# Section 2.2 — Data Structure


async def test_a_token_carries_every_claim_the_profile_requires() -> None:
    # "iss — REQUIRED", "exp — REQUIRED", "aud — REQUIRED", "sub — REQUIRED",
    # "client_id — REQUIRED", "iat — REQUIRED", "jti — REQUIRED" (section 2.2).
    claims = claims_of(await _issued_token())

    for required in ("iss", "exp", "aud", "sub", "client_id", "iat", "jti"):
        assert required in claims, f"{required} is missing"
    assert claims["iss"] == ISSUER
    assert claims["client_id"] == CLIENT_ID


async def test_a_token_a_client_was_issued_for_itself_names_the_client_as_subject() -> None:
    # "In cases of access tokens obtained through grants where no resource
    # owner is involved, such as the client credentials grant, the value of
    # "sub" SHOULD correspond to an identifier the authorization server uses to
    # indicate the client application" (section 2.2).
    claims = claims_of(await _issued_token())

    assert claims["sub"] == CLIENT_ID


async def test_a_tokens_window_is_a_pair_of_whole_seconds() -> None:
    # ``iat``, ``nbf`` and ``exp`` are the NumericDate of the standard section
    # 2.2 builds on, which is a number of seconds.
    claims = claims_of(await _issued_token())

    for name in ("iat", "nbf", "exp"):
        assert isinstance(claims[name], int), f"{name} is {claims[name]!r}"
    issued_at = claims["iat"]
    expires_at = claims["exp"]
    assert isinstance(issued_at, int)
    assert isinstance(expires_at, int)
    assert expires_at > issued_at


async def test_a_token_names_what_it_may_do_as_space_delimited_text() -> None:
    # "If an authorization request includes a scope parameter, the
    # corresponding issued JWT access token SHOULD include a "scope" claim"
    # (section 2.2.3), which the standard it borrows the claim from writes as a
    # space-delimited string.
    async with serving(_application()) as client:
        seeded = await client.post(SEED_PATH, params={"scope": "read write"})
        assert seeded.status_code == 200, seeded.text
        issued = json_of(
            await client.post(
                "/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "scope": "read write",
                },
            ),
        )
        token = text_field(issued, "access_token")

    scope = claims_of(token)["scope"]
    assert isinstance(scope, str)
    assert set(scope.split(" ")) == {"read", "write"}


def test_the_claims_the_profile_defines_cannot_be_written_over() -> None:
    # A deployment adding claims of its own may not redefine the ones section
    # 2.2 requires, or the token would no longer say what the profile says it
    # says.
    assert set(RESERVED_CLAIMS) == {
        "aud",
        "client_id",
        "exp",
        "iat",
        "iss",
        "jti",
        "nbf",
        "scope",
        "sub",
    }


# Section 4 — Validating JWT Access Tokens


async def test_a_token_declaring_another_media_type_is_refused() -> None:
    # "The resource server MUST verify that the "typ" header value is "at+jwt"
    # or "application/at+jwt" and reject tokens carrying any other value"
    # (section 4).
    token = _signed(header={"typ": "JWT", "kid": KEY_ID})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert refusal.value.get_error_type() == "access_denied"


async def test_a_token_declaring_the_full_media_type_is_accepted() -> None:
    # The other half of the same sentence: "MUST verify that the "typ" header
    # value is "at+jwt" or "application/at+jwt"" (section 4).
    token = _signed(header={"typ": FULL_TYPE_HEADER, "kid": KEY_ID})

    claims = await _validator().validate_bearer_token(_request(f"Bearer {token}"), token)

    assert claims["jti"] == "access-1"


async def test_a_token_naming_another_issuer_is_refused() -> None:
    # "The issuer identifier for the authorization server ... MUST exactly
    # match the value of the "iss" claim" (section 4).
    token = _signed({"iss": "https://somebody-else.example.com"})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert "issuer" in str(refusal.value.get_hint())


async def test_a_token_signed_with_no_algorithm_at_all_is_refused() -> None:
    # "The resource server MUST reject any JWT in which the value of "alg" is
    # "none"" (section 4).
    token = _unsigned({"alg": "none", "typ": TYPE_HEADER}, _CLAIMS)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert refusal.value.get_error_type() == "access_denied"


async def test_a_token_no_trusted_key_signed_is_refused() -> None:
    # "The resource server MUST validate the signature of all incoming JWT
    # access tokens ... MUST use the keys provided by the authorization server"
    # (section 4).
    token = await _issued_token()
    tampered = f"{token[:-4]}AAAA"

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {tampered}"))

    assert refusal.value.get_error_type() == "access_denied"


async def test_a_token_whose_window_has_closed_is_refused() -> None:
    # "The current time MUST be before the time represented by the "exp" claim"
    # (section 4).
    token = _signed({"exp": _NOW - 1})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert "expired" in str(refusal.value.get_hint())


async def test_a_token_addressed_to_the_resource_that_reads_it_is_accepted() -> None:
    # "The resource server MUST validate that the "aud" claim contains a
    # resource indicator value corresponding to an identifier the resource
    # server expects for itself" (section 4), read in a deployment that names
    # one.
    async with serving(_audience_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert claims_of(token)["aud"] == AUDIENCE
    assert answered.status_code == 200


async def test_a_token_addressed_elsewhere_is_refused() -> None:
    # "The JWT access token MUST be rejected if "aud" does not contain a
    # resource indicator of the current resource server as a valid audience"
    # (section 4).
    token = _signed({"aud": "https://somebody-elses-resource.example.com"})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator(AUDIENCE).validate_authorization(_request(f"Bearer {token}"))

    assert "audience" in str(refusal.value.get_hint())


async def test_a_deployment_naming_no_audience_does_not_check_one() -> None:
    # A deployment that configures no audience addresses each token to the
    # client it was issued to and checks nothing. Section 4 requires the check,
    # so this is a recorded deviation (plan, Phase 5) rather than a reading of
    # the standard — pinned here so it cannot change unnoticed.
    token = _signed({"aud": "whoever"})

    claims = await _validator().validate_bearer_token(_request(f"Bearer {token}"), token)

    assert claims["aud"] == "whoever"


async def test_a_refusal_names_the_error_code_the_profile_requires() -> None:
    # "The resource server MUST handle errors as described in Section 3.1 of
    # [RFC6750]. In particular, in case of any failure in the validation checks
    # listed above, the authorization server response MUST include the error
    # code "invalid_token"" (section 4).
    async with serving(_application()) as client:
        answered = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer not.a.token"},
        )

    assert answered.status_code == 401
    named = f"{answered.headers.get('www-authenticate', '')} {answered.text}"
    assert "invalid_token" in named


async def test_a_refused_token_opens_nothing() -> None:
    # Whatever the refusal is called, the check itself is what section 4 is
    # about: a token that fails it serves nobody.
    async with serving(_application()) as client:
        answered = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer not.a.token"},
        )

    assert answered.status_code == 401
    assert "read" not in json_of(answered)


# Section 5 — Security Considerations


async def test_two_tokens_never_share_an_identifier() -> None:
    # "To prevent cross-JWT confusion, authorization servers MUST use a
    # distinct identifier as the "aud" claim value ... " rests on the token
    # being distinguishable; the ``jti`` of section 2.2 is what makes one
    # token's revocation not another's.
    async with serving(_application()) as client:
        first = await client_credentials_token(client)
        second = await client_credentials_token(client)

    assert claims_of(first)["jti"] != claims_of(second)["jti"]


async def test_the_words_a_refusal_carries_never_name_the_token() -> None:
    # Section 6 asks that nothing about a token leak; a refusal that quoted the
    # token would put a credential in a log.
    token = _signed({"exp": _NOW - 1})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await _validator().validate_authorization(_request(f"Bearer {token}"))

    assert token not in str(refusal.value)
    assert token not in str(refusal.value.get_hint())
