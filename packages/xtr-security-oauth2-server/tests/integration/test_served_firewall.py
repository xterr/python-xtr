"""An API read by this deployment's own access tokens, served for real.

One process issues the tokens and reads them, which is the deployment the
resource-server side is documented for: the firewall on ``/api`` accepts
exactly what the token endpoint hands out.
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import APIRouter, FastAPI
from xtr_dependency_injection import Injected
from xtr_security import Security
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider

from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    client_credentials_token,
    json_of,
    oauth2_kernel,
    served_application,
    serving,
    text_field,
    text_fields,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx

pytestmark = pytest.mark.anyio

FIREWALL = "api"


def _api(app: FastAPI) -> None:
    """Mount an API behind the firewall that reads this server's access tokens."""
    # The dependency is handed to the router before any route is added: the
    # framework copies a router's dependencies into each route as it arrives.
    router = APIRouter(prefix="/api")

    @router.get("/me")
    async def me(security: Injected[Security]) -> dict[str, object]:
        token = security.get_token()
        assert token is not None

        return {
            "caller": token.get_user_identifier(),
            "roles": list(token.get_role_names()),
        }

    @router.get("/writable")
    async def writable() -> dict[str, str]:
        return {"wrote": "yes"}

    app.include_router(router)


def _application() -> FastAPI:
    """Return the served application with its API behind the firewall."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_firewall_app"),
        _api,
    )


async def test_a_request_carrying_no_token_is_challenged_for_one() -> None:
    async with serving(_application()) as client:
        answered = await client.get("/api/me")

    assert answered.status_code == 401
    # The challenge says what would have worked, and nothing else: RFC 6750
    # section 3 has the scheme followed by one or more auth-param values, and
    # section 3.1 asks that a request lacking any authentication information
    # be told no error code.
    assert answered.headers["www-authenticate"] == f'Bearer realm="{FIREWALL}"'


async def test_the_challenge_is_never_cached() -> None:
    # A proxy answering another caller's request with one principal's refusal
    # would be telling the wrong person something about the right one.
    async with serving(_application()) as client:
        answered = await client.get("/api/me")

    assert answered.headers["cache-control"] == "no-store"


async def test_a_token_a_client_was_issued_for_itself_names_the_client_as_the_caller() -> None:
    # Such a token belongs to no person, so the client stands where a resource
    # owner would.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert answered.status_code == 200
    assert text_field(json_of(answered), "caller") == CLIENT_ID


async def test_a_scope_reaches_the_authorization_rules_as_a_role() -> None:
    # What lets an access token be checked by exactly the same rules as
    # everything else.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert "ROLE_OAUTH2_READ" in text_fields(json_of(answered), "roles")


async def test_a_token_without_the_scope_a_route_asks_for_is_refused() -> None:
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get("/api/writable", headers={"Authorization": f"Bearer {token}"})

    assert answered.status_code == 403
    # What the caller is told, not only that it was refused: RFC 6750 2 names
    # ``insufficient_scope`` for a token good enough to prove the caller and
    # not good enough for what it asked to do — in the challenge header, the
    # one place RFC 6750 reserves for it, and nowhere in the body.
    assert answered.text == ""
    assert 'error="insufficient_scope"' in answered.headers["WWW-Authenticate"]
    assert answered.headers["WWW-Authenticate"].startswith("Bearer")


async def test_a_token_this_server_did_not_sign_is_refused() -> None:
    async with serving(_application()) as client:
        answered = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer not.a.token"},
        )

    assert answered.status_code == 401


async def test_a_request_whose_header_names_another_scheme_is_not_claimed() -> None:
    # This authenticator reads bearer tokens; anything else is somebody
    # else's to answer, and with no other authenticator the firewall
    # challenges.
    async with serving(_application()) as client:
        answered = await client.get(
            "/api/me",
            headers={"Authorization": "Basic YWRhOnNlY3JldA=="},
        )

    assert answered.status_code == 401


async def test_a_withdrawn_token_stops_opening_the_api() -> None:
    # What withdrawing a token is *for*: the reading an API does has to judge
    # revocation against the same store the withdrawal wrote to, or a token
    # given up would keep working until it expired.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        bearer = {"Authorization": f"Bearer {token}"}
        before = await client.get("/api/me", headers=bearer)
        withdrawn = await client.post(
            "/revoke",
            data={
                "token": token,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        after = await client.get("/api/me", headers=bearer)

    assert before.status_code == 200
    assert withdrawn.status_code == 200
    assert after.status_code == 401


def _recording_route(reached: list[str]) -> Callable[[FastAPI], None]:
    """Mount ``/api/open``, a route behind the firewall that notes each time it runs."""

    def extend(app: FastAPI) -> None:
        router = APIRouter(prefix="/api")

        @router.get("/open")
        async def open_route() -> dict[str, str]:
            reached.append("open")

            return {"read": "yes"}

        app.include_router(router)

    return extend


def _too_deep_to_read() -> str:
    """Return a token whose claims nest a thousand arrays deep, under a signature no key made."""
    parts = (b'{"alg":"RS256","typ":"JWT"}', b"[" * 1000 + b"]" * 1000, b"x" * 32)

    return ".".join(base64.urlsafe_b64encode(part).rstrip(b"=").decode() for part in parts)


def _decoder_hitting_its_depth_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every JSON decode of nested arrays give up, as the oldest interpreter's does.

    Whether a document a thousand arrays deep exhausts the decoder depends on
    the interpreter; this makes it do so on every one.
    """
    loads = json.loads

    def limited(document: str | bytes, cls: type[json.JSONDecoder] | None = None) -> object:
        text = document.encode() if isinstance(document, str) else bytes(document)
        if b"[[" in text:
            message = "maximum recursion depth exceeded while decoding a JSON array"
            raise RecursionError(message)
        return cast("object", loads(document, cls=cls))

    monkeypatch.setattr(json, "loads", limited)


async def _ask_with(token: str) -> tuple[httpx.Response, list[str]]:
    """Present ``token`` to ``/api/open``, answering what the caller got and whether it ran."""
    reached: list[str] = []
    application = served_application(
        oauth2_kernel("tests.fixtures.oauth2_firewall_app"),
        _recording_route(reached),
    )
    async with serving(application, raise_app_exceptions=False) as client:
        answered = await client.get("/api/open", headers={"Authorization": f"Bearer {token}"})

    return answered, reached


async def test_a_reader_failing_unexpectedly_keeps_the_api_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A failure nobody answers is no reason to skip the rest of the firewall:
    # the access rule on ``/api`` would never be asked, and the route would
    # run for nobody. The request fails instead.
    def _broken(provider: JoserfcJwsProvider, token: str) -> None:
        del provider, token
        message = "the token reader broke"
        raise RuntimeError(message)

    monkeypatch.setattr(JoserfcJwsProvider, "load", _broken)
    answered, reached = await _ask_with("a.b.c")

    assert answered.status_code == 500
    assert reached == []


async def test_a_token_too_deep_to_read_is_refused_as_an_invalid_token() -> None:
    answered, reached = await _ask_with(_too_deep_to_read())

    assert answered.status_code == 401
    assert 'error="invalid_token"' in answered.headers["www-authenticate"]
    assert reached == []


async def test_a_token_too_deep_to_read_is_refused_whatever_the_decoder_gives_up_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _decoder_hitting_its_depth_limit(monkeypatch)

    answered, reached = await _ask_with(_too_deep_to_read())

    assert answered.status_code == 401
    assert 'error="invalid_token"' in answered.headers["www-authenticate"]
    assert reached == []


@pytest.mark.parametrize(
    "header",
    [
        b'{"alg":"RS256","crit":5}',
        b'{"alg":"RS256","crit":[["a"]]}',
        b'["alg"]',
        b'"alg"',
    ],
)
async def test_a_token_whose_header_cannot_be_judged_is_refused_as_an_invalid_token(
    header: bytes,
) -> None:
    parts = (header, b"{}", b"x" * 32)
    token = ".".join(base64.urlsafe_b64encode(part).rstrip(b"=").decode() for part in parts)

    answered, reached = await _ask_with(token)

    assert answered.status_code == 401
    assert 'error="invalid_token"' in answered.headers["www-authenticate"]
    assert reached == []
