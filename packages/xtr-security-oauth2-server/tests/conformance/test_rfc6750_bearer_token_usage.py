"""RFC 6750 — The OAuth 2.0 Authorization Framework: Bearer Token Usage.

What a resource server owes a caller: the one way it accepts a token, and the
challenge it answers with when it will not. Driven through a served
application whose API sits behind the authenticator this package ships, since
every requirement here is about what reaches the caller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest
from fastapi import APIRouter, FastAPI

from tests.support.served import (
    client_credentials_token,
    json_of,
    oauth2_kernel,
    served_application,
    serving,
)

if TYPE_CHECKING:
    import httpx

pytestmark = pytest.mark.anyio

FIREWALL: Final = "api"

#: The characters the standard allows in a ``scope`` attribute value: %x21 /
#: %x23-5B / %x5D-7E for the names, and %x20 between them.
SCOPE_CHARACTERS: Final = frozenset(
    {chr(point) for point in (0x20, 0x21, *range(0x23, 0x5C), *range(0x5D, 0x7F))},
)

#: The characters the standard allows in ``error`` and ``error_description``:
#: %x20-21 / %x23-5B / %x5D-7E.
ERROR_CHARACTERS: Final = frozenset(
    {chr(point) for point in (*range(0x20, 0x22), *range(0x23, 0x5C), *range(0x5D, 0x7F))},
)


def _api(app: FastAPI) -> None:
    """Mount an API behind the firewall that reads this server's access tokens."""
    router = APIRouter(prefix="/api")

    @router.get("/me")
    async def me() -> dict[str, str]:
        return {"read": "yes"}

    @router.get("/writable")
    async def writable() -> dict[str, str]:
        return {"wrote": "yes"}

    app.include_router(router)


def _application() -> FastAPI:
    """Return a deployment whose API is read by its own access tokens."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_firewall_app"),
        extend=_api,
    )


def _challenge(response: httpx.Response) -> str:
    """Return the challenge the answer carries."""
    return response.headers["www-authenticate"]


def _attribute_count(challenge: str, name: str) -> int:
    """Count how often ``name=`` appears as an attribute of ``challenge``."""
    return sum(1 for part in challenge.split(",") if part.strip().startswith(f"{name}="))


# Section 2.1 — Authorization Request Header Field


async def test_a_token_is_accepted_in_the_authorization_header() -> None:
    # "Clients SHOULD make authenticated requests with a bearer token using
    # the "Authorization" request header field with the "Bearer" HTTP
    # authorization scheme. Resource servers MUST support this method"
    # (section 2.1).
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert answered.status_code == 200


async def test_the_scheme_is_read_whatever_case_it_was_written_in() -> None:
    # Section 2.1 writes the credentials as ``"Bearer" 1*SP b64token`` on top
    # of the HTTP authentication framework, whose scheme name is
    # case-insensitive (RFC 9110 section 11.1), so a caller writing it
    # differently is still presenting a bearer token.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get("/api/me", headers={"Authorization": f"bearer {token}"})

    assert answered.status_code == 200
    assert json_of(answered) == {"read": "yes"}


# Section 3 — The WWW-Authenticate Response Header Field


async def test_a_request_carrying_no_token_is_answered_with_a_challenge() -> None:
    # "If the protected resource request does not include authentication
    # credentials ... the resource server MUST include the HTTP
    # "WWW-Authenticate" response header field" (section 3).
    async with serving(_application()) as client:
        answered = await client.get("/api/me")

    assert answered.status_code == 401
    assert "www-authenticate" in answered.headers


async def test_a_token_this_server_cannot_read_is_answered_with_a_challenge() -> None:
    # "or does not contain an access token that enables access to the
    # protected resource, the resource server MUST include the HTTP
    # "WWW-Authenticate" response header field" (section 3).
    async with serving(_application()) as client:
        answered = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer not.a.token"},
        )

    assert answered.status_code == 401
    assert "www-authenticate" in answered.headers


async def test_every_challenge_names_the_bearer_scheme() -> None:
    # "All challenges defined by this specification MUST use the auth-scheme
    # value "Bearer"" (section 3).
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        nothing_presented = await client.get("/api/me")
        unreadable = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer not.a.token"},
        )
        too_little = await client.get(
            "/api/writable",
            headers={"Authorization": f"Bearer {token}"},
        )

    for answered in (nothing_presented, unreadable, too_little):
        assert _challenge(answered).startswith("Bearer"), _challenge(answered)


async def test_the_challenge_for_an_unread_token_carries_an_attribute() -> None:
    # "This scheme MUST be followed by one or more auth-param values"
    # (section 3). The request that presented nothing is named a realm, and
    # the refused token an error code, which section 3.1 is what decides.
    async with serving(_application()) as client:
        nothing_presented = await client.get("/api/me")
        unreadable = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer not.a.token"},
        )

    for answered in (nothing_presented, unreadable):
        assert _challenge(answered).strip() != "Bearer"


async def test_the_challenge_for_too_little_privilege_carries_attributes() -> None:
    # The same rule, met where the answer has something to say: a token good
    # enough to prove the caller and not good enough for what it asked
    # (section 3).
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get(
            "/api/writable",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert _challenge(answered) != "Bearer"
    assert 'error="insufficient_scope"' in _challenge(answered)


async def test_no_attribute_of_a_challenge_is_written_twice() -> None:
    # "A "realm" attribute MUST NOT appear more than once", "The "scope"
    # attribute MUST NOT appear more than once", and ""error",
    # "error_description", and "error_uri" attributes MUST NOT appear more than
    # once" (section 3).
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get(
            "/api/writable",
            headers={"Authorization": f"Bearer {token}"},
        )

    challenge = _challenge(answered)
    for name in ("realm", "scope", "error", "error_description", "error_uri"):
        assert _attribute_count(challenge, name) <= 1, f"{name} appears twice in {challenge}"


async def test_the_words_a_challenge_uses_stay_inside_the_allowed_characters() -> None:
    # "Values for the "scope" attribute MUST NOT include characters outside the
    # set %x21 / %x23-5B / %x5D-7E ... and %x20 for delimiters", and the
    # ``error`` and ``error_description`` values MUST NOT include characters
    # outside %x20-21 / %x23-5B / %x5D-7E (section 3).
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get(
            "/api/writable",
            headers={"Authorization": f"Bearer {token}"},
        )

    for part in _challenge(answered).split(","):
        name, _, raw = part.strip().partition("=")
        value = raw.strip('"')
        allowed = SCOPE_CHARACTERS if name == "scope" else ERROR_CHARACTERS
        if name in {"scope", "error", "error_description"}:
            assert set(value) <= allowed, f"{name} carries {set(value) - allowed!r}"


# Section 3.1 — Error Codes


async def test_a_token_lacking_the_privilege_asked_for_says_so() -> None:
    # "insufficient_scope — The request requires higher privileges than
    # provided by the access token. The resource server SHOULD respond with the
    # HTTP 403 (Forbidden) status code and MAY include the "scope" attribute
    # with the scope necessary to access the protected resource" (section 3.1).
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.get(
            "/api/writable",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert answered.status_code == 403
    # The challenge header carries the error code — the body carries nothing,
    # so no scope detail leaks anywhere but the header RFC 6750 reserves for it.
    assert answered.text == ""
    assert 'error="insufficient_scope"' in _challenge(answered)
    assert 'scope="write"' in _challenge(answered)


async def test_a_request_that_presented_nothing_is_told_no_reason() -> None:
    # "If the request lacks any authentication information ... the resource
    # server SHOULD NOT include an error code or other error information"
    # (section 3.1).
    async with serving(_application()) as client:
        answered = await client.get("/api/me")

    assert "error=" not in _challenge(answered)
    assert "error" not in json_of(answered)
