"""An add-on's flow, answer, contribution and route, served for real.

The deployment beside this one runs the shipped redirect flow; this one runs an
add-on's. Both are driven the same way, over ASGI, against a live container —
what a test asserts on is what a client would receive, and every one of these
answers is produced by code the package knows nothing about, reached only
through the extension points it documents.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl, urlsplit

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_security_http.firewall.firewall import Firewall

from tests.fixtures.extension_app.bundle import OWN_ACCESS_TOKEN_TTL, ExtensionBundle
from tests.fixtures.extension_app.config import (
    AUTH_CODE_TTL,
    OPEN_PROOF_KEY_ENV,
    REFRESH_TOKEN_TTL,
    USER_IDENTIFIER,
    USER_PASSWORD,
)
from tests.fixtures.extension_app.contributor import CONTRIBUTED_FIELD
from tests.fixtures.extension_app.grant import NONCE_PARAMETER
from tests.fixtures.extension_app.response_type import NONCE_FIELD
from tests.fixtures.extension_app.routes import USERINFO_PATH, extension_routes
from tests.fixtures.extension_app.stamp import STAMP_PREFIX
from tests.support.encryption import unseal
from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    SCOPE,
    SEED_PATH,
    code_challenge_of,
    int_field,
    json_of,
    served_application,
    serving,
    text_field,
    text_fields,
)
from tests.support.signing import ISSUER
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

pytestmark = pytest.mark.anyio

#: A proof key, within the length the standard allows, and the challenge a
#: client derives from it.
VERIFIER: Final = "a-code-verifier-long-enough-for-the-standard"
CHALLENGE: Final = code_challenge_of(VERIFIER)

#: What ties the redirect back to the browser that started the flow.
STATE: Final = "the-opaque-state"

#: The parameter the add-on carries from the authorization request, through the
#: code, into the token answer.
NONCE: Final = "n-0S6_WzA2Mj"

PUBLIC_CLIENT_ID: Final = "a-public-client"

#: The firewall the fixture application puts in front of the add-on's route,
#: which is the protection space its bearer challenge names.
FIREWALL: Final = "api"


def _kernel(env: str = "test") -> Kernel:
    """Return a kernel running this package's bundle and the add-on's beside it.

    ``env`` picks which of the deployment's two environments is served, which
    is how a test chooses whether a public client must commit to a proof key.
    """
    return Kernel(
        "tests.fixtures.extension_app",
        env=env,
        bundles={OAuth2ServerBundle: {"all": True}, ExtensionBundle: {"all": True}},
        concurrent_scoped_access=True,
    )


def _mount_the_add_ons_route(app: FastAPI) -> None:
    """Include the router the add-on ships, as an application includes any."""
    app.include_router(extension_routes())


def _application(env: str = "test") -> FastAPI:
    """Return the served application of the add-on's deployment.

    The firewall goes on the application, unbound, so it stands in front of
    both the authorization endpoint — where the resource owner is established
    before anybody is asked to approve — and the add-on's own route. The token
    endpoint stays outside it, as always.
    """
    return served_application(
        _kernel(env),
        _mount_the_add_ons_route,
        dependencies=[Firewall()],
    )


async def _seed(client: httpx.AsyncClient) -> None:
    """Register a confidential client that may drive both flows."""
    seeded = await client.post(
        SEED_PATH,
        params={"grant": "", "redirect_uri": REDIRECT_URI},
    )
    # A seed that quietly failed would surface far away, as a client that
    # cannot authenticate.
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


async def _authorize(
    client: httpx.AsyncClient,
    token: str,
    nonce: str | None = NONCE,
    challenge: str | None = CHALLENGE,
    client_id: str = CLIENT_ID,
) -> httpx.Response:
    """Ask for an authorization code as the established resource owner."""
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "state": STATE,
        "scope": SCOPE,
    }
    if nonce is not None:
        query[NONCE_PARAMETER] = nonce
    if challenge is not None:
        query["code_challenge"] = challenge
        query["code_challenge_method"] = "S256"

    return await client.get(
        "/authorize",
        params=query,
        headers={"Authorization": f"Bearer {token}"},
    )


def _delivered(answered: httpx.Response) -> Mapping[str, str]:
    """Return the parameters the redirect ``answered`` sent the browser back with.

    Only for an answer that is a redirect: a refusal carries no such header at
    all, and a caller that might have met one says so itself before reading
    what was delivered.
    """
    return dict(parse_qsl(urlsplit(answered.headers["location"]).query))


async def _code(client: httpx.AsyncClient, nonce: str | None = NONCE) -> str:
    """Drive the first half of the flow and return the code it issued."""
    await _seed(client)
    answered = await _authorize(client, await _owner_token(client), nonce)
    delivered = _delivered(answered)
    # An authorization response that carried a refusal instead of a code should
    # say so here, not as a missing key.
    assert "code" in delivered, f"{answered.status_code}: {delivered}"

    return delivered["code"]


async def _redeem(client: httpx.AsyncClient, code: str) -> httpx.Response:
    """Redeem ``code`` for a token pair, as the client that started the flow."""
    return await client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": VERIFIER,
        },
    )


async def _issued(client: httpx.AsyncClient) -> Mapping[str, object]:
    """Drive the whole flow and return the token answer it ended in."""
    answered = await _redeem(client, await _code(client))
    assert answered.status_code == 200, answered.text

    return json_of(answered)


async def _issued_without_a_nonce(client: httpx.AsyncClient) -> Mapping[str, object]:
    """Drive the flow with no parameter of the add-on's, and return the answer."""
    answered = await _redeem(client, await _code(client, nonce=None))
    assert answered.status_code == 200, answered.text

    return json_of(answered)


async def _authorized_as_a_public_client(client: httpx.AsyncClient) -> httpx.Response:
    """Register a client holding no secret and ask for a code with no proof key.

    The one request the proof-key requirement decides, driven the same way
    against both environments so that only the setting differs.
    """
    await _seed(client)
    _ = await client.post(
        SEED_PATH,
        params={
            "identifier": PUBLIC_CLIENT_ID,
            "secret": "",
            "grant": "",
            "redirect_uri": REDIRECT_URI,
        },
    )

    return await _authorize(
        client,
        await _owner_token(client),
        challenge=None,
        client_id=PUBLIC_CLIENT_ID,
    )


def _seconds_left(carried: Mapping[str, object]) -> int:
    """Return how long the credential ``carried`` was sealed out of has left."""
    return int_field(carried, "expire_time") - int(datetime.now(UTC).timestamp())


async def test_a_code_exchange_answers_the_field_built_from_the_carried_parameter() -> None:
    # The whole of the add-on's flow in one answer: a parameter read off the
    # authorization request, remembered across consent, sealed into the code,
    # read back at the token endpoint, and published by an answer the container
    # built with the add-on's own service.
    async with serving(_application()) as client:
        issued = await _issued(client)

    assert text_field(issued, NONCE_FIELD) == f"{STAMP_PREFIX}:{NONCE}"


async def test_the_answer_still_carries_what_the_flow_itself_defines() -> None:
    # An add-on adds a field; it does not get to replace the ones a client
    # reads by name.
    async with serving(_application()) as client:
        issued = await _issued(client)

    assert text_field(issued, "access_token")
    assert text_field(issued, "refresh_token")
    assert text_field(issued, "token_type") == "Bearer"


async def test_a_code_carrying_no_such_parameter_is_redeemed_without_the_field() -> None:
    # The parameter is the add-on's, not the protocol's, so a request that sent
    # none is an ordinary request and gets an ordinary answer.
    async with serving(_application()) as client:
        issued = await _issued_without_a_nonce(client)

    assert NONCE_FIELD not in issued


async def test_the_contributed_grant_issues_for_the_lifetime_its_tag_names() -> None:
    # A lifetime of the grant's own, which only a tag attribute can say — and
    # the deployment's own access-token lifetime is an hour, so a token lasting
    # three minutes can have come from nowhere else.
    async with serving(_application()) as client:
        issued = await _issued(client)

    expected = int(OWN_ACCESS_TOKEN_TTL.total_seconds())
    assert int_field(issued, "expires_in") in range(expected - 5, expected + 1)


async def test_the_contributed_grant_issues_codes_for_the_lifetime_the_deployment_set() -> None:
    # A tagged grant is handed none of the settings a shipped one is given, so
    # the add-on read this off the deployment's configuration and set it on the
    # definition. Seven minutes, where the grant's own default is ten.
    async with serving(_application()) as client:
        code = await _code(client)

    expected = int(AUTH_CODE_TTL.total_seconds())
    assert _seconds_left(unseal(code)) in range(expected - 5, expected + 1)


async def test_the_contributed_grant_issues_refresh_tokens_for_the_deployments_lifetime() -> None:
    # The same again for the other lifetime the add-on had to read and set:
    # nine days, where the grant's own default is thirty.
    async with serving(_application()) as client:
        issued = await _issued(client)

    expected = int(REFRESH_TOKEN_TTL.total_seconds())
    carried = unseal(text_field(issued, "refresh_token"))
    assert _seconds_left(carried) in range(expected - 5, expected + 1)


async def test_a_public_client_must_still_commit_to_a_proof_key() -> None:
    # The other setting the add-on had to read and honour: a client holding no
    # secret has nothing else to prove it is the one the code was issued to.
    async with serving(_application()) as client:
        answered = await _authorized_as_a_public_client(client)

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_public_client_commits_to_none_where_the_deployment_requires_none() -> None:
    # The same grant, the same client, the same request — and a code rather
    # than that refusal, because this environment turns the requirement off.
    # A grant deciding the requirement for itself would answer one of these
    # two twice.
    async with serving(_application(OPEN_PROOF_KEY_ENV)) as client:
        answered = await _authorized_as_a_public_client(client)

    # The refusal above answers in a document, so a request that met one says
    # so with that document rather than as a missing redirect.
    assert answered.status_code == 302, answered.text
    assert "code" in _delivered(answered)


async def test_the_description_this_server_publishes_holds_the_contributed_field() -> None:
    # A capability nothing in this package knows about, published where a client
    # looks for one.
    async with serving(_application()) as client:
        described = json_of(await client.get("/.well-known/oauth-authorization-server"))

    assert described[CONTRIBUTED_FIELD] is True


async def test_the_description_still_says_what_this_server_decided_itself() -> None:
    # A contribution is merged underneath this server's own fields, never over
    # them.
    async with serving(_application()) as client:
        described = json_of(await client.get("/.well-known/oauth-authorization-server"))

    assert text_field(described, "issuer")
    assert text_field(described, "token_endpoint")


async def test_the_description_names_the_add_ons_flow_among_those_the_server_runs() -> None:
    # The add-on turned the shipped redirect flow off and runs its own under the
    # same name, so the flow is still one this server runs.
    async with serving(_application()) as client:
        described = json_of(await client.get("/.well-known/oauth-authorization-server"))

    assert "authorization_code" in text_fields(described, "grant_types_supported")


async def test_the_description_names_where_the_add_ons_flow_starts() -> None:
    async with serving(_application()) as client:
        described = json_of(await client.get("/.well-known/oauth-authorization-server"))

    assert text_field(described, "authorization_endpoint") == f"{ISSUER}/authorize"


async def test_the_description_names_the_response_the_add_ons_flow_asks_for() -> None:
    async with serving(_application()) as client:
        described = json_of(await client.get("/.well-known/oauth-authorization-server"))

    assert text_fields(described, "response_types_supported") == ["code"]


async def test_the_add_ons_route_challenges_a_request_carrying_no_token() -> None:
    async with serving(_application()) as client:
        answered = await client.get(USERINFO_PATH)

    assert answered.status_code == 401
    # The challenge says what would have worked, and names the firewall as
    # its protection space: RFC 6750 section 3 has the scheme followed by one
    # or more auth-param values, and section 3.1 asks that a request lacking
    # any authentication information be told no error code.
    assert answered.headers["www-authenticate"] == f'Bearer realm="{FIREWALL}"'


async def test_the_add_ons_route_answers_a_caller_this_server_issued_a_token_to() -> None:
    # An add-on's endpoint sits behind the authenticator this package ships, so
    # it reads exactly the tokens this server hands out.
    async with serving(_application()) as client:
        await _seed(client)
        token = await _owner_token(client)
        answered = await client.get(
            USERINFO_PATH,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert answered.status_code == 200
    assert text_field(json_of(answered), "owner") == USER_IDENTIFIER
