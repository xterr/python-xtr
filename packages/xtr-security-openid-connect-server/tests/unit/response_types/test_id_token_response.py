"""The token answer of a sign-in carries a signed ID token beside the access token."""

from __future__ import annotations

import copy
import json
from datetime import timedelta
from typing import TYPE_CHECKING, cast, final

import pytest
from joserfc import jwt
from typing_extensions import override
from xtr_http_message import Response
from xtr_security_jwt.services.jws_provider import JwsProviderInterface
from xtr_security_jwt.signature.created_jws import CreatedJws
from xtr_security_oauth2_server_core.entities.access_token_signer import AccessTokenSigner
from xtr_security_oauth2_server_core.response_types.bearer_token_response import BearerTokenResponse

from tests.support.entities import AccessToken, make_client, make_scope
from tests.support.signing import (
    ALGORITHMS,
    EDDSA_DEPRECATION,
    FROZEN_NOW,
    ISSUER,
    edwards_key,
    make_clock,
    make_edwards_signer,
    make_signer,
    signing_key,
)
from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)
from xtr_security_openid_connect_server.id_token_settings import IdTokenSettings
from xtr_security_openid_connect_server.response_types.id_token_response import IdTokenResponse
from xtr_security_openid_connect_server.token_hash import token_hash

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_jwt.signature.loaded_jws import LoadedJws

_AN_HOUR = timedelta(hours=1)
_AUTH_TIME = int(FROZEN_NOW.timestamp()) - 30
_NONCE = "n-0S6_WzA2Mj"

pytestmark = pytest.mark.anyio


def _access_token(
    signer: AccessTokenSigner,
    scopes: tuple[str, ...] = ("openid", "profile"),
) -> AccessToken:
    token = AccessToken()
    token.set_identifier("access-1")
    token.set_client(make_client("my-client"))
    for scope in scopes:
        token.add_scope(make_scope(scope))
    token.set_user_identifier("alice")
    token.set_expiry_date_time(FROZEN_NOW + _AN_HOUR)
    token.set_private_key(signer)
    return token


def _response(
    algorithm: str,
    ttl: timedelta | None = None,
    signer: AccessTokenSigner | None = None,
) -> IdTokenResponse:
    return IdTokenResponse(
        make_clock(),
        signer if signer is not None else make_signer(algorithm),
        IdTokenSettings(algorithm=algorithm, ttl=ttl),
    )


async def _body(response_type: IdTokenResponse) -> Mapping[str, object]:
    answer = await response_type.generate_http_response(Response())
    return cast("Mapping[str, object]", json.loads(await answer.get_body().get_contents()))


async def _signed_in(
    algorithm: str,
    ttl: timedelta | None = None,
    audience: str | None = None,
) -> tuple[Mapping[str, object], jwt.Token]:
    signer = make_signer(algorithm, audience)
    response_type = _response(algorithm, ttl, signer)
    response_type.set_access_token(_access_token(signer))
    response_type.set_identity("alice", "my-client", _AUTH_TIME, _NONCE)
    body = await _body(response_type)
    id_token = jwt.decode(str(body["id_token"]), signing_key(algorithm), algorithms=[algorithm])
    return body, id_token


def test_it_is_the_bearer_answer() -> None:
    assert isinstance(_response("RS256"), BearerTokenResponse)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
async def test_the_id_token_makes_identity_claims_only(algorithm: str) -> None:
    _, id_token = await _signed_in(algorithm)

    assert set(id_token.claims) == {
        "iss",
        "sub",
        "aud",
        "exp",
        "iat",
        "auth_time",
        "nonce",
        "at_hash",
    }
    assert id_token.claims["iss"] == ISSUER
    assert id_token.claims["sub"] == "alice"
    assert id_token.claims["iat"] == int(FROZEN_NOW.timestamp())
    assert id_token.claims["auth_time"] == _AUTH_TIME
    assert id_token.claims["nonce"] == _NONCE


@pytest.mark.parametrize("algorithm", ALGORITHMS)
async def test_it_is_addressed_to_the_client_not_the_access_token_audience(
    algorithm: str,
) -> None:
    _, id_token = await _signed_in(algorithm, audience="https://api.example.com")

    assert id_token.claims["aud"] == "my-client"


@pytest.mark.parametrize("algorithm", ALGORITHMS)
async def test_a_configured_lifetime_decides_the_expiry(algorithm: str) -> None:
    _, id_token = await _signed_in(algorithm, ttl=timedelta(minutes=5))

    assert id_token.claims["exp"] - id_token.claims["iat"] == 300


@pytest.mark.parametrize("algorithm", ALGORITHMS)
async def test_with_no_lifetime_it_expires_with_the_access_token(algorithm: str) -> None:
    _, id_token = await _signed_in(algorithm)

    assert id_token.claims["exp"] == int((FROZEN_NOW + _AN_HOUR).timestamp())


@pytest.mark.parametrize("algorithm", ALGORITHMS)
async def test_at_hash_is_the_hash_of_the_access_token_the_client_receives(
    algorithm: str,
) -> None:
    body, id_token = await _signed_in(algorithm)

    assert id_token.claims["at_hash"] == token_hash(str(body["access_token"]), algorithm)


@pytest.mark.filterwarnings(EDDSA_DEPRECATION)
async def test_at_hash_over_an_ed448_key_is_the_hash_its_curve_names() -> None:
    signer = make_edwards_signer("Ed448")
    response_type = IdTokenResponse(
        make_clock(),
        signer,
        IdTokenSettings(algorithm="EdDSA", curve="Ed448"),
    )
    response_type.set_access_token(_access_token(signer))
    response_type.set_identity("alice", "my-client", None, None)

    body = await _body(response_type)
    claims = jwt.decode(str(body["id_token"]), edwards_key("Ed448"), algorithms=["EdDSA"]).claims

    assert claims["at_hash"] == token_hash(str(body["access_token"]), "EdDSA", "Ed448")


@pytest.mark.parametrize("algorithm", ALGORITHMS)
async def test_the_header_names_the_type_the_algorithm_and_the_key(algorithm: str) -> None:
    _, id_token = await _signed_in(algorithm)

    assert id_token.header["typ"] == "JWT"
    assert id_token.header["alg"] == algorithm
    assert id_token.header["kid"] == make_signer(algorithm).key_id


async def test_an_unknown_auth_time_and_an_absent_nonce_are_left_out() -> None:
    signer = make_signer("RS256")
    response_type = _response("RS256", signer=signer)
    response_type.set_access_token(_access_token(signer))
    response_type.set_identity("alice", "my-client", None, None)

    body = await _body(response_type)
    claims = jwt.decode(str(body["id_token"]), signing_key("RS256"), algorithms=["RS256"]).claims

    assert "auth_time" not in claims
    assert "nonce" not in claims


async def test_with_no_identity_there_is_no_id_token() -> None:
    signer = make_signer("RS256")
    response_type = _response("RS256", signer=signer)
    response_type.set_access_token(_access_token(signer))

    assert "id_token" not in await _body(response_type)


async def test_without_the_openid_scope_there_is_no_id_token() -> None:
    signer = make_signer("RS256")
    response_type = _response("RS256", signer=signer)
    response_type.set_access_token(_access_token(signer, ("profile", "email")))
    response_type.set_identity("alice", "my-client", _AUTH_TIME, _NONCE)

    assert "id_token" not in await _body(response_type)


async def test_a_copy_keeps_its_identity_to_itself() -> None:
    # The server hands every token request a shallow copy of one answer, so
    # one request's sign-in must never reach another request's answer.
    signer = make_signer("RS256")
    template = _response("RS256", signer=signer)
    first = copy.copy(template)
    second = copy.copy(template)
    first.set_identity("alice", "my-client", _AUTH_TIME, _NONCE)
    for answer in (first, template, second):
        answer.set_access_token(_access_token(signer))

    assert "id_token" in await _body(first)
    assert "id_token" not in await _body(template)
    assert "id_token" not in await _body(second)


def test_the_identity_it_records_is_scalars_only() -> None:
    # Scalars are what a shallow copy may share safely: nothing a later request
    # sets can reach through them into an earlier request's answer.
    before = _response("RS256")
    after = copy.copy(before)
    after.set_identity("alice", "my-client", _AUTH_TIME, _NONCE)
    held_before = cast("dict[str, object]", vars(before))
    held_after = cast("dict[str, object]", vars(after))

    recorded = {
        name: value for name, value in held_after.items() if held_before.get(name) is not value
    }

    assert recorded
    assert all(isinstance(value, str | int | None) for value in recorded.values())


@final
class _UnsignedJwsProvider(JwsProviderInterface):
    """Answers with a token it says it did not sign, as a misconfigured provider would."""

    @override
    def create(
        self,
        payload: Mapping[str, object],
        header: Mapping[str, object] | None = None,
    ) -> CreatedJws:
        return CreatedJws("unsigned", is_signed=False)

    @override
    def load(self, token: str) -> LoadedJws:
        raise NotImplementedError


async def test_an_unsigned_id_token_is_refused() -> None:
    clock = make_clock()
    signer = make_signer("RS256")
    unsigned = AccessTokenSigner(
        jws_provider=_UnsignedJwsProvider(),
        key_id=signer.key_id,
        issuer=ISSUER,
        clock=clock,
    )
    response_type = IdTokenResponse(clock, unsigned, IdTokenSettings(algorithm="RS256"))
    response_type.set_access_token(_access_token(signer))
    response_type.set_identity("alice", "my-client", None, None)

    with pytest.raises(InvalidArgumentError, match="unsigned"):
        _ = await response_type.generate_http_response(Response())
