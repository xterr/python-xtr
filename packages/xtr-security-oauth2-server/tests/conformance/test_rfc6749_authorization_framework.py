"""RFC 6749 — The OAuth 2.0 Authorization Framework.

Every test names the section it answers for. Where a case comes from the test
suite of oauthlib 4.0.0 (145a9a4) or aioauth 2.0.1 (81365d3) rather than from
the text of the standard, the test says which.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from xtr_security_http.firewall.firewall import Firewall

from tests.fixtures.oauth2_auth_code_app.config import USER_IDENTIFIER, USER_PASSWORD
from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    SCOPE,
    SEED_PATH,
    code_challenge_of,
    json_of,
    oauth2_kernel,
    served_application,
    serving,
    text_field,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio

#: A proof key within the length the standard allows, and the challenge tying
#: an authorization request to it.
VERIFIER: Final = "a-code-verifier-long-enough-for-the-standard"
CHALLENGE: Final = code_challenge_of(VERIFIER)

#: What ties the redirect back to the browser that started the flow.
STATE: Final = "the-opaque-state"

#: A second registered client, for the rules about which client a grant was
#: issued to.
OTHER_CLIENT_ID: Final = "another-confidential-client"
OTHER_CLIENT_SECRET: Final = "another-plaintext-secret"

#: The characters the standard allows in an ``error`` or ``error_description``:
#: %x20-21 / %x23-5B / %x5D-7E — printable ASCII without the double quote and
#: the backslash.
ERROR_CHARACTERS: Final = frozenset(
    {chr(point) for point in (*range(0x20, 0x22), *range(0x23, 0x5C), *range(0x5D, 0x7F))},
)


def _application() -> FastAPI:
    """Return a deployment running the redirect flow and the flows beside it.

    The firewall goes on the application rather than on the router this package
    ships, which is what establishes the resource owner on the authorization
    endpoint; the token endpoint stays outside it, because authenticating the
    *client* there is this server's own job.
    """
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_auth_code_app"),
        dependencies=[Firewall()],
    )


def _basic(client_id: str, secret: str) -> str:
    """Return the ``Authorization`` header a client authenticating with Basic sends."""
    encoded = base64.b64encode(f"{client_id}:{secret}".encode()).decode("ascii")

    return f"Basic {encoded}"


async def _seed(client: httpx.AsyncClient, **params: str) -> None:
    """Register a client that may drive every flow, and fail loudly if it did not."""
    query = {"grant": "", "redirect_uri": REDIRECT_URI, **params}
    seeded = await client.post(SEED_PATH, params=query)
    assert seeded.status_code == 200, seeded.text


async def _owner_token(client: httpx.AsyncClient) -> str:
    """Establish the resource owner, and return the token that proves them."""
    issued = json_of(
        await client.post(
            "/token",
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": USER_IDENTIFIER,
                "password": USER_PASSWORD,
                "scope": SCOPE,
            },
        ),
    )

    return text_field(issued, "access_token")


def _delivered(response: httpx.Response) -> Mapping[str, str]:
    """Return the parameters an authorization response was delivered in."""
    return dict(parse_qsl(urlsplit(response.headers["location"]).query))


async def _authorize(
    client: httpx.AsyncClient,
    token: str,
    **extra: str,
) -> httpx.Response:
    """Ask for an authorization code as the established resource owner."""
    query = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": STATE,
        "scope": SCOPE,
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        **extra,
    }

    return await client.get(
        "/authorize",
        params=query,
        headers={"Authorization": f"Bearer {token}"},
    )


async def _code(client: httpx.AsyncClient) -> str:
    """Drive the first half of the redirect flow and return the code it issued."""
    await _seed(client)
    answered = await _authorize(client, await _owner_token(client))
    delivered = _delivered(answered)
    assert "code" in delivered, f"{answered.status_code}: {delivered}"

    return delivered["code"]


async def _redeem(client: httpx.AsyncClient, **extra: str) -> httpx.Response:
    """Exchange a freshly issued code, overriding whatever the caller names."""
    form = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": await _code(client),
        "code_verifier": VERIFIER,
        **extra,
    }

    return await client.post("/token", data=form)


# Section 2.3.1 — Client Password


async def test_a_client_may_authenticate_with_the_basic_scheme() -> None:
    # "The authorization server MUST support the HTTP Basic authentication
    # scheme for authenticating client credentials" (section 2.3.1).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": _basic(CLIENT_ID, CLIENT_SECRET)},
        )

    assert answered.status_code == 200
    assert text_field(json_of(answered), "access_token")


async def test_a_client_may_authenticate_in_the_request_body() -> None:
    # The body form is permitted beside the header (section 2.3.1), and it is
    # what every other test here uses.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )

    assert answered.status_code == 200


# Section 3.1 — Authorization Endpoint


async def test_the_authorization_endpoint_answers_a_get() -> None:
    # "The authorization server MUST support the use of the HTTP GET method
    # for the authorization endpoint" (section 3.1).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(client, await _owner_token(client))

    assert answered.status_code == 302


async def test_a_parameter_this_server_does_not_know_is_ignored() -> None:
    # "The authorization server MUST ignore unrecognized request parameters"
    # (section 3.1).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(
            client,
            await _owner_token(client),
            something_nobody_defined="whatever",
        )

    assert answered.status_code == 302
    assert _delivered(answered)["code"]


async def test_a_repeated_response_type_is_refused_before_a_grant_is_chosen() -> None:
    # "Request and response parameters MUST NOT be included more than once"
    # (section 3.1), for the one parameter that decides which flow reads the
    # request. It is refused before any grant is offered the request, so no
    # flow has to agree on which of the two values was meant.
    async with serving(_application()) as client:
        await _seed(client)
        owner = await _owner_token(client)
        answered = await client.get(
            "/authorize",
            params=[
                ("response_type", "code"),
                ("response_type", "code"),
                ("client_id", CLIENT_ID),
                ("redirect_uri", REDIRECT_URI),
                ("state", STATE),
                ("scope", SCOPE),
                ("code_challenge", CHALLENGE),
                ("code_challenge_method", "S256"),
            ],
            headers={"Authorization": f"Bearer {owner}"},
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_parameter_sent_without_a_value_counts_as_omitted() -> None:
    # "Parameters sent without a value MUST be treated as if they were omitted
    # from the request" (section 3.1). A scope sent empty is therefore not an
    # empty scope but no scope at all, which the client's registration fills.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": "",
            },
        )

    assert answered.status_code == 200


# Section 3.1.2.3 — Dynamic Configuration


async def test_a_redirect_uri_the_client_never_registered_is_refused() -> None:
    # "the authorization server MUST compare and match the value received
    # against at least one of the registered redirection URIs" (section
    # 3.1.2.3).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(
            client,
            await _owner_token(client),
            redirect_uri="https://attacker.test/callback",
        )

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"


# Section 3.1.2.4 — Invalid Endpoint


async def test_a_refusal_about_the_redirect_uri_is_not_itself_a_redirect() -> None:
    # "If the request fails due to a missing, invalid, or mismatching
    # redirection URI ... MUST NOT automatically redirect the user-agent to the
    # invalid redirection URI" (section 3.1.2.4).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(
            client,
            await _owner_token(client),
            redirect_uri="https://attacker.test/callback",
        )

    assert "location" not in answered.headers


# Section 3.2 — Token Endpoint


async def test_the_token_endpoint_ignores_a_parameter_it_does_not_know() -> None:
    # "The authorization server MUST ignore unrecognized request parameters"
    # (section 3.2).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "nobody_defined_this": "whatever",
            },
        )

    assert answered.status_code == 200


async def test_a_parameter_the_request_repeats_is_refused() -> None:
    # "Request and response parameters MUST NOT be included more than once"
    # (section 3.2); section 5.2 catalogues a request that "repeats a
    # parameter" under ``invalid_request``. Ported from oauthlib's
    # ``test_invalid_request`` and ``test_invalid_request_duplicate_params``
    # (tests/oauth2/rfc6749/endpoints/test_error_responses.py).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            content="grant_type=client_credentials"
            f"&client_id={CLIENT_ID}&client_id=somebody-else"
            f"&client_secret={CLIENT_SECRET}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_repeated_grant_type_is_refused_before_a_grant_is_chosen() -> None:
    # The same rule for the one parameter that decides *which* flow reads the
    # request (sections 3.2 and 5.2). Repeating it is refused whether the two
    # values agree or not: a server that read the last one would let a hop
    # append a grant type the client never asked for.
    async with serving(_application()) as client:
        await _seed(client)
        credentials = f"&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}"
        twice_the_same = await client.post(
            "/token",
            content=f"grant_type=client_credentials&grant_type=client_credentials{credentials}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        two_different = await client.post(
            "/token",
            content=f"grant_type=client_credentials&grant_type=password{credentials}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert twice_the_same.status_code == 400
    assert text_field(json_of(twice_the_same), "error") == "invalid_request"
    assert two_different.status_code == 400
    assert text_field(json_of(two_different), "error") == "invalid_request"


# Section 3.3 — Access Token Scope


async def test_a_grant_that_differs_from_the_request_names_the_scope_it_gave() -> None:
    # "If the issued access token scope is different from the one requested by
    # the client, the authorization server MUST include the "scope" response
    # parameter to inform the client of the actual scope granted" (section
    # 3.3). A request naming no scope is granted the client's registered ones,
    # which is a scope the client did not ask for.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )

    assert text_field(json_of(answered), "scope") == SCOPE


# Section 4.1.2 — Authorization Response


async def test_the_authorization_response_carries_the_state_it_was_sent() -> None:
    # "state — REQUIRED if the "state" parameter was present in the client
    # authorization request. The exact value received from the client"
    # (section 4.1.2).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(client, await _owner_token(client))

    assert _delivered(answered)["state"] == STATE


async def test_a_code_used_a_second_time_is_denied() -> None:
    # "The client MUST NOT use the authorization code more than once. If an
    # authorization code is used more than once, the authorization server MUST
    # deny the request" (section 4.1.2): the very form that was just honoured,
    # sent a second time, is refused.
    async with serving(_application()) as client:
        code = await _code(client)
        form = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": VERIFIER,
        }
        first = await client.post("/token", data=form)
        again = await client.post("/token", data=form)

    assert first.status_code == 200
    assert again.status_code == 400
    assert text_field(json_of(again), "error") == "invalid_grant"


# Section 4.1.2.1 / 5.2 — Error Response


async def test_the_words_a_refusal_uses_stay_inside_the_allowed_characters() -> None:
    # "Values for the "error" parameter MUST NOT include characters outside the
    # set %x20-21 / %x23-5B / %x5D-7E", and the same for "error_description"
    # (sections 4.1.2.1 and 5.2).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={"grant_type": "client_credentials", "client_id": CLIENT_ID},
        )

    refused = json_of(answered)
    for name in ("error", "error_description"):
        value = text_field(refused, name)
        assert set(value) <= ERROR_CHARACTERS, f"{name} carries {set(value) - ERROR_CHARACTERS!r}"


async def test_a_client_that_tried_the_basic_scheme_is_told_which_scheme_to_try() -> None:
    # "If the client attempted to authenticate via the "Authorization" request
    # header field, the authorization server MUST respond with an HTTP 401
    # (Unauthorized) status code and include the "WWW-Authenticate" response
    # header field matching the authentication scheme used by the client"
    # (section 5.2).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": _basic(CLIENT_ID, "the-wrong-secret")},
        )

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"
    assert answered.headers["www-authenticate"].startswith("Basic ")


async def test_a_grant_type_this_server_does_not_run_is_named_as_unsupported() -> None:
    # The ``unsupported_grant_type`` code of section 5.2. Ported from
    # oauthlib's ``test_unsupported_grant_type``
    # (tests/oauth2/rfc6749/endpoints/test_error_responses.py).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "nothing-like-a-grant",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "unsupported_grant_type"


# Section 4.1.3 — Access Token Request


async def test_a_code_is_redeemed_only_against_the_redirect_uri_it_was_tied_to() -> None:
    # "ensure that the "redirect_uri" parameter is present if the
    # "redirect_uri" parameter was included in the initial authorization
    # request ... and if included ensure that their values are identical"
    # (section 4.1.3). The refusal is named ``invalid_request`` rather than the
    # ``invalid_grant`` section 5.2 catalogues for a code that "does not match
    # the redirection URI used in the authorization request" — a naming this
    # suite's README records among the deliberate deviations; the rule itself
    # is enforced.
    async with serving(_application()) as client:
        answered = await _redeem(client, redirect_uri="https://client.test/elsewhere")

    assert answered.status_code == 400
    refused = json_of(answered)
    assert "access_token" not in refused
    assert text_field(refused, "error") == "invalid_request"


async def test_a_code_is_refused_when_the_redirect_uri_is_left_out() -> None:
    # The same rule read the other way: the authorization request named one, so
    # the token request must too (section 4.1.3).
    async with serving(_application()) as client:
        code = await _code(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "code_verifier": VERIFIER,
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_code_cannot_be_redeemed_by_another_client() -> None:
    # "ensure that the authorization code was issued to the authenticated
    # confidential client" (section 4.1.3): another client, authenticating as
    # itself, presents the code and is refused. Named ``invalid_request`` — a
    # deliberate deviation this suite's README records — where section 5.2
    # catalogues a grant "issued to another client" under ``invalid_grant``;
    # the denial itself is what section 4.1.3 requires.
    async with serving(_application()) as client:
        code = await _code(client)
        await _seed(
            client,
            identifier=OTHER_CLIENT_ID,
            secret=OTHER_CLIENT_SECRET,
        )
        answered = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": OTHER_CLIENT_ID,
                "client_secret": OTHER_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": code,
                "code_verifier": VERIFIER,
            },
        )

    assert answered.status_code == 400
    refused = json_of(answered)
    assert "access_token" not in refused
    assert text_field(refused, "error") == "invalid_request"


async def test_a_confidential_client_must_authenticate_to_redeem_a_code() -> None:
    # "require client authentication for confidential clients or for any client
    # that was issued client credentials" (section 4.1.3). A confidential
    # client that sent no secret is told which parameter is missing rather than
    # being counted as a failed authentication, so the answer is
    # ``invalid_request``/400 where section 5.2 catalogues "no client
    # authentication included" under ``invalid_client``; the requirement — no
    # token without client authentication — is enforced either way.
    async with serving(_application()) as client:
        answered = await _redeem(client, client_secret="")

    assert answered.status_code == 400
    refused = json_of(answered)
    assert "access_token" not in refused
    assert text_field(refused, "error") == "invalid_request"


# Section 4.3.2 — Resource Owner Password Credentials


async def test_credentials_this_server_does_not_accept_are_refused() -> None:
    # "validate the resource owner password credentials using its existing
    # password validation algorithm" (section 4.3.2).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": USER_IDENTIFIER,
                "password": "not-the-password",
                "scope": SCOPE,
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_grant"


# Section 4.4.2 — Client Credentials


async def test_a_client_acting_for_itself_must_authenticate() -> None:
    # "The authorization server MUST authenticate the client" (section 4.4.2).
    # A client naming itself with a secret that is not its own is refused.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": "the-wrong-secret",
            },
        )

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"


# Section 5.1 — Successful Response


async def test_the_token_answer_names_the_scheme_and_what_is_left_of_the_lifetime() -> None:
    # "access_token — REQUIRED", "token_type — REQUIRED", "expires_in —
    # RECOMMENDED" (section 5.1).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )

    issued = json_of(answered)
    assert text_field(issued, "token_type") == "Bearer"
    assert isinstance(issued["expires_in"], int)
    assert issued["expires_in"] > 0


async def test_an_answer_carrying_a_token_may_not_be_cached() -> None:
    # "The authorization server MUST include the HTTP "Cache-Control" response
    # header field with a value of "no-store" in any response containing
    # tokens ... as well as the "Pragma" response header field with a value of
    # "no-cache"" (section 5.1).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )

    assert answered.headers["cache-control"] == "no-store"
    assert answered.headers["pragma"] == "no-cache"


# Section 6 — Refreshing an Access Token


async def _refresh_token(client: httpx.AsyncClient) -> str:
    """Drive the redirect flow to a token pair and return the refresh token.

    The client is registered for both scopes while the resource owner grants
    one, so that a scope the client is *registered* for can still be one that
    was never granted.
    """
    await _seed(client, scope="read write")
    issued = json_of(await _redeem(client))

    return text_field(issued, "refresh_token")


async def test_a_refresh_token_cannot_be_spent_by_another_client() -> None:
    # "ensure that the refresh token was issued to the authenticated client"
    # (section 6): another client, authenticating as itself, presents the
    # refresh token and is refused.
    async with serving(_application()) as client:
        refresh = await _refresh_token(client)
        await _seed(client, identifier=OTHER_CLIENT_ID, secret=OTHER_CLIENT_SECRET)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": OTHER_CLIENT_ID,
                "client_secret": OTHER_CLIENT_SECRET,
                "refresh_token": refresh,
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_grant"


async def test_a_refresh_may_not_ask_for_a_scope_that_was_never_granted() -> None:
    # "The requested scope MUST NOT include any scope not originally granted by
    # the resource owner" (section 6). The client is registered for the wider
    # scope, so what refuses the request is the grant it was given.
    async with serving(_application()) as client:
        refresh = await _refresh_token(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": refresh,
                "scope": "write",
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_scope"


async def test_a_refresh_token_that_was_already_spent_is_invalid() -> None:
    # "validate the refresh token" (section 6); section 5.2 names
    # ``invalid_grant`` for "a refresh token [that] is invalid, expired,
    # revoked", and that is the answer a refresh token already spent gets.
    async with serving(_application()) as client:
        refresh = await _refresh_token(client)
        form = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": refresh,
        }
        first = await client.post("/token", data=form)
        again = await client.post("/token", data=form)

    assert first.status_code == 200
    assert again.status_code == 400
    assert text_field(json_of(again), "error") == "invalid_grant"


async def test_a_refresh_token_this_server_cannot_read_is_invalid() -> None:
    # The same rule for a token that was never issued here: one this server
    # cannot read is as invalid as one it has seen spent.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": "nothing-this-server-sealed",
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_grant"
