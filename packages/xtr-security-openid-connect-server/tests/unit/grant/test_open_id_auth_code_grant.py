"""The authorization code flow carries a sign-in from the authorize step to the token.

Every test here runs the grant inside an authorization server built by hand,
over in-memory storage and a real signer, the way a deployment without a
container builds one: the code a test redeems is one the grant itself sealed.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import timedelta
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlsplit

import pytest
from joserfc import jwt
from xtr_event_dispatcher import EventDispatcher
from xtr_http_message import Response, ServerRequest
from xtr_security_oauth2_server.entity import Client, User
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.grant.auth_code_grant import AuthCodeGrant

from tests.support.encryption import ENCRYPTION_KEY, seal, unseal
from tests.support.repositories import (
    InMemoryAccessTokenRepository,
    InMemoryAuthCodeRepository,
    InMemoryClientRepository,
    InMemoryRefreshTokenRepository,
    InMemoryScopeRepository,
)
from tests.support.signing import FROZEN_NOW, make_clock, make_signer, signing_key
from xtr_security_openid_connect_server.grant.open_id_auth_code_grant import OpenIdAuthCodeGrant
from xtr_security_openid_connect_server.id_token_settings import IdTokenSettings
from xtr_security_openid_connect_server.request_types.open_id_authorization_request import (
    OpenIdAuthorizationRequest,
)
from xtr_security_openid_connect_server.response_types.id_token_response import IdTokenResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import MockClock
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

pytestmark = pytest.mark.anyio

_REDIRECT_URI = "https://client.test/callback"
_NONCE = "n-0S6_WzA2Mj"
_AUTH_TIME = int(FROZEN_NOW.timestamp()) - 30
_CODE_TTL = timedelta(minutes=10)
_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"


def _client(identifier: str, *, confidential: bool) -> Client:
    client = Client()
    client.set_identifier(identifier)
    client.set_name(identifier)
    client.set_redirect_uri([_REDIRECT_URI])
    client.set_confidential(confidential)
    return client


def _grant(clock: MockClock, *, require_code_challenge: bool = True) -> OpenIdAuthCodeGrant:
    return OpenIdAuthCodeGrant(
        EventDispatcher(),
        clock,
        InMemoryAuthCodeRepository(),
        InMemoryRefreshTokenRepository(),
        _CODE_TTL,
        timedelta(days=7),
        require_code_challenge,
    )


def _id_token_response(clock: MockClock) -> IdTokenResponse:
    return IdTokenResponse(
        clock,
        make_signer("RS256", clock=clock),
        IdTokenSettings(algorithm="RS256"),
    )


def _server(
    clock: MockClock,
    grant: OpenIdAuthCodeGrant,
    response_type: ResponseTypeInterface | None,
) -> AuthorizationServer:
    clients = InMemoryClientRepository()
    clients.add(_client("my-client", confidential=True), "s3cret")
    clients.add(_client("public-client", confidential=False))
    server = AuthorizationServer(
        clients,
        InMemoryAccessTokenRepository(),
        InMemoryScopeRepository("openid", "profile"),
        make_signer("RS256", clock=clock),
        ENCRYPTION_KEY,
        "key",
        EventDispatcher(),
        response_type,
    )
    server.enable_grant_type(grant)
    return server


def _sign_in_server(
    clock: MockClock, *, require_code_challenge: bool = True
) -> AuthorizationServer:
    return _server(
        clock,
        _grant(clock, require_code_challenge=require_code_challenge),
        _id_token_response(clock),
    )


def _authorize(**extra: str) -> ServerRequestInterface:
    query = {
        "response_type": "code",
        "client_id": "my-client",
        "redirect_uri": _REDIRECT_URI,
        "scope": "openid profile",
        "state": "xyz",
        **extra,
    }
    return ServerRequest("GET", "/authorize").with_query_params(query)


async def _validated(server: AuthorizationServer, **extra: str) -> OpenIdAuthorizationRequest:
    authorization_request = await server.validate_authorization_request(_authorize(**extra))
    assert isinstance(authorization_request, OpenIdAuthorizationRequest)
    return authorization_request


async def _code(
    server: AuthorizationServer,
    auth_time: int | None = _AUTH_TIME,
    **extra: str,
) -> str:
    """Run the authorize step as alice, signed in at ``auth_time``, and return the code."""
    authorization_request = await _validated(server, **extra)
    authorization_request.set_auth_time(auth_time)
    alice = User()
    alice.set_identifier("alice")
    authorization_request.set_user(alice)
    authorization_request.set_authorization_approved(True)
    answer = await server.complete_authorization_request(
        _authorize(**extra),
        authorization_request,
        Response(),
    )
    location = answer.get_header_line("Location")
    return parse_qs(urlsplit(location).query)["code"][0]


def _token_request(code: str, **extra: str) -> ServerRequestInterface:
    body = {
        "grant_type": "authorization_code",
        "client_id": "my-client",
        "client_secret": "s3cret",
        "redirect_uri": _REDIRECT_URI,
        "code": code,
        **extra,
    }
    return ServerRequest("POST", "/token").with_parsed_body(body)


async def _redeem(
    server: AuthorizationServer, request: ServerRequestInterface
) -> Mapping[str, object]:
    answer = await server.respond_to_access_token_request(request, Response())
    return cast("Mapping[str, object]", json.loads(await answer.get_body().get_contents()))


def _claims(body: Mapping[str, object]) -> Mapping[str, object]:
    return jwt.decode(str(body["id_token"]), signing_key("RS256"), algorithms=["RS256"]).claims


def test_it_is_the_shipped_code_flow() -> None:
    assert isinstance(_grant(make_clock()), AuthCodeGrant)


def test_it_records_what_it_reads_into_a_sign_in_request() -> None:
    assert isinstance(
        _grant(make_clock()).create_authorization_request(), OpenIdAuthorizationRequest
    )


async def test_it_reads_the_nonce_the_prompt_and_the_max_age() -> None:
    server = _sign_in_server(make_clock())

    authorization_request = await _validated(
        server,
        nonce=_NONCE,
        prompt="login consent",
        max_age="600",
    )

    assert authorization_request.get_nonce() == _NONCE
    assert authorization_request.get_prompt() == frozenset({"login", "consent"})
    assert authorization_request.get_max_age() == 600


async def test_a_request_asking_none_of_them_carries_none() -> None:
    authorization_request = await _validated(_sign_in_server(make_clock()))

    assert authorization_request.get_nonce() is None
    assert authorization_request.get_prompt() == frozenset()
    assert authorization_request.get_max_age() is None


async def test_a_max_age_of_zero_is_kept() -> None:
    authorization_request = await _validated(_sign_in_server(make_clock()), max_age="0")

    assert authorization_request.get_max_age() == 0


async def test_prompt_none_beside_another_value_is_an_invalid_request() -> None:
    with pytest.raises(OAuthServerError) as raised:
        _ = await _validated(_sign_in_server(make_clock()), prompt="none login")

    assert raised.value.get_error_type() == "invalid_request"


@pytest.mark.parametrize("max_age", ["soon", "-1", "1.5", "+5", "1e3", "\u0663"])
async def test_a_max_age_that_is_no_whole_number_of_seconds_is_an_invalid_request(
    max_age: str,
) -> None:
    with pytest.raises(OAuthServerError) as raised:
        _ = await _validated(_sign_in_server(make_clock()), max_age=max_age)

    assert raised.value.get_error_type() == "invalid_request"
    assert "max_age" in str(raised.value.get_hint())


def _naming_no_redirect_uri(**extra: str) -> ServerRequestInterface:
    query = _authorize(**extra).get_query_params()
    return ServerRequest("GET", "/authorize").with_query_params(
        {name: value for name, value in query.items() if name != "redirect_uri"},
    )


async def test_a_sign_in_naming_no_redirect_uri_is_an_invalid_request() -> None:
    server = _sign_in_server(make_clock())

    with pytest.raises(OAuthServerError) as raised:
        _ = await server.validate_authorization_request(_naming_no_redirect_uri())

    assert raised.value.get_error_type() == "invalid_request"
    assert "redirect_uri" in str(raised.value.get_hint())


async def test_a_sign_in_naming_no_redirect_uri_is_answered_as_a_document() -> None:
    server = _sign_in_server(make_clock())
    with pytest.raises(OAuthServerError) as raised:
        _ = await server.validate_authorization_request(_naming_no_redirect_uri())

    answer = await raised.value.generate_http_response(Response())

    assert answer.get_status_code() == 400
    assert not answer.has_header("Location")


async def test_a_request_without_openid_may_leave_the_redirect_uri_out() -> None:
    server = _sign_in_server(make_clock())
    request = _naming_no_redirect_uri(scope="profile")
    authorization_request = await server.validate_authorization_request(request)
    alice = User()
    alice.set_identifier("alice")
    authorization_request.set_user(alice)
    authorization_request.set_authorization_approved(True)

    answer = await server.complete_authorization_request(request, authorization_request, Response())

    assert answer.get_header_line("Location").startswith(f"{_REDIRECT_URI}?")


async def test_the_code_carries_the_nonce_and_the_auth_time() -> None:
    code = await _code(_sign_in_server(make_clock()), nonce=_NONCE)

    payload = unseal(code)

    assert payload["nonce"] == _NONCE
    assert payload["auth_time"] == _AUTH_TIME


async def test_a_code_for_a_request_without_them_carries_neither() -> None:
    payload = unseal(await _code(_sign_in_server(make_clock()), auth_time=None))

    assert "nonce" not in payload
    assert "auth_time" not in payload


async def test_a_sign_in_is_answered_with_an_id_token_carrying_the_nonce() -> None:
    server = _sign_in_server(make_clock())
    code = await _code(server, nonce=_NONCE)

    claims = _claims(await _redeem(server, _token_request(code)))

    assert claims["nonce"] == _NONCE
    assert claims["sub"] == "alice"
    assert claims["aud"] == "my-client"
    assert claims["auth_time"] == _AUTH_TIME


async def test_a_sign_in_without_nonce_or_auth_time_leaves_both_out() -> None:
    server = _sign_in_server(make_clock())
    code = await _code(server, auth_time=None)

    claims = _claims(await _redeem(server, _token_request(code)))

    assert "nonce" not in claims
    assert "auth_time" not in claims


async def test_a_flow_without_the_openid_scope_has_no_id_token() -> None:
    server = _sign_in_server(make_clock())
    code = await _code(server, scope="profile")

    assert "id_token" not in await _redeem(server, _token_request(code))


async def test_a_code_naming_no_resource_owner_is_answered_without_an_id_token() -> None:
    clock = make_clock()
    server = _sign_in_server(clock)
    code = seal(
        {
            "client_id": "my-client",
            "redirect_uri": _REDIRECT_URI,
            "auth_code_id": "code-1",
            "scopes": ["openid"],
            "expire_time": int(FROZEN_NOW.timestamp()) + 60,
            "nonce": _NONCE,
        }
    )

    body = await _redeem(server, _token_request(code))

    assert "access_token" in body
    assert "id_token" not in body


async def test_the_bearer_answer_is_refused_as_this_servers_own_mistake() -> None:
    clock = make_clock()
    server = _server(clock, _grant(clock), None)
    code = await _code(server, nonce=_NONCE)

    with pytest.raises(OAuthServerError) as raised:
        _ = await _redeem(server, _token_request(code))

    assert raised.value.get_error_type() == "server_error"
    assert "response_type_class" in str(raised.value)


async def test_an_expired_code_is_an_invalid_grant() -> None:
    clock = make_clock()
    server = _sign_in_server(clock)
    code = await _code(server, nonce=_NONCE)
    clock.sleep(_CODE_TTL.total_seconds() + 1)

    with pytest.raises(OAuthServerError) as raised:
        _ = await _redeem(server, _token_request(code))

    assert raised.value.get_error_type() == "invalid_grant"


def _public_token_request(code: str) -> ServerRequestInterface:
    body = {
        "grant_type": "authorization_code",
        "client_id": "public-client",
        "redirect_uri": _REDIRECT_URI,
        "code": code,
    }
    return ServerRequest("POST", "/token").with_parsed_body(body)


async def test_a_public_client_needs_a_proof_key_by_default() -> None:
    with pytest.raises(OAuthServerError) as raised:
        _ = await _validated(_sign_in_server(make_clock()), client_id="public-client")

    assert raised.value.get_error_type() == "invalid_request"


async def test_a_deployment_may_let_a_public_client_sign_in_without_a_proof_key() -> None:
    server = _sign_in_server(make_clock(), require_code_challenge=False)
    code = await _code(server, client_id="public-client", nonce=_NONCE)

    body = await _redeem(server, _public_token_request(code))

    assert _claims(body)["aud"] == "public-client"


async def test_a_public_client_signs_in_with_a_proof_key() -> None:
    server = _sign_in_server(make_clock())
    digest = hashlib.sha256(_VERIFIER.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    code = await _code(
        server,
        client_id="public-client",
        code_challenge=challenge,
        code_challenge_method="S256",
    )
    request = _public_token_request(code)
    body = cast("dict[str, str]", request.get_parsed_body()) | {"code_verifier": _VERIFIER}

    answer = await _redeem(server, request.with_parsed_body(body))

    assert _claims(answer)["sub"] == "alice"


async def test_the_refresh_lifetime_it_was_built_with_is_the_one_it_issues() -> None:
    server = _sign_in_server(make_clock())
    code = await _code(server)

    body = await _redeem(server, _token_request(code))

    refresh = unseal(str(body["refresh_token"]))
    assert refresh["expire_time"] == int((FROZEN_NOW + timedelta(days=7)).timestamp())


async def test_a_code_that_cannot_be_read_back_is_an_invalid_request() -> None:
    server = _sign_in_server(make_clock())

    with pytest.raises(OAuthServerError) as raised:
        _ = await _redeem(server, _token_request("not-a-code"))

    assert raised.value.get_error_type() == "invalid_request"
