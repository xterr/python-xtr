"""The userinfo endpoint served for real, answering only a signed-in user's own token.

Each test serves the fixture deployment in the environment it is about and
reads the endpoint the way a client would: the status, the headers and the
document are what went over the wire.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest

from tests.fixtures.openid_app.config import (
    IDENTITY_PROVIDER_ENV,
    USER_IDENTIFIER,
    USER_PASSWORD,
    USERINFO_ENV,
)
from tests.support.served import (
    SERVICE_CLIENT_ID,
    SERVICE_CLIENT_SECRET,
    json_of,
    openid_kernel,
    served_application,
    serving,
    text_field,
)
from xtr_security_openid_connect_server.exception import InvalidConfigurationError

if TYPE_CHECKING:
    import httpx

pytestmark = pytest.mark.anyio

#: Where the endpoint is served by default.
USERINFO: Final = "/userinfo"

#: What the fixture's identity provider says of alice, as a grant of ``profile``
#: and ``email`` reveals it.
ALICES_CLAIMS: Final = {
    "sub": "alice",
    "name": "Alice",
    "email": "alice@example.com",
    "email_verified": True,
}


async def _owner_token(client: httpx.AsyncClient, scope: str) -> str:
    """Return an access token alice was issued, carrying ``scope``."""
    issued = await client.post(
        "/token",
        data={
            "grant_type": "password",
            "client_id": SERVICE_CLIENT_ID,
            "client_secret": SERVICE_CLIENT_SECRET,
            "username": USER_IDENTIFIER,
            "password": USER_PASSWORD,
            "scope": scope,
        },
    )
    assert issued.status_code == 200, issued.text

    return text_field(json_of(issued), "access_token")


async def _service_token(client: httpx.AsyncClient, scope: str) -> str:
    """Return an access token the client was issued for itself, carrying ``scope``."""
    issued = await client.post(
        "/token",
        data={
            "grant_type": "client_credentials",
            "client_id": SERVICE_CLIENT_ID,
            "client_secret": SERVICE_CLIENT_SECRET,
            "scope": scope,
        },
    )
    assert issued.status_code == 200, issued.text

    return text_field(json_of(issued), "access_token")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _read_with_a_token(scope: str) -> httpx.Response:
    """Serve the claims-reading deployment and read the endpoint with alice's token."""
    async with serving(served_application(openid_kernel(USERINFO_ENV))) as client:
        token = await _owner_token(client, scope)
        return await client.get(USERINFO, headers=_bearer(token))


async def test_the_signed_in_users_claims_are_answered_as_the_scopes_reveal_them() -> None:
    answered = await _read_with_a_token("openid profile email")

    assert answered.status_code == 200, answered.text
    assert json_of(answered) == ALICES_CLAIMS


async def test_the_answer_is_a_document_no_cache_keeps() -> None:
    answered = await _read_with_a_token("openid profile email")

    assert answered.headers["content-type"] == "application/json"
    assert answered.headers["cache-control"] == "no-store"


async def test_a_scope_revealing_nothing_answers_the_subject_alone() -> None:
    answered = await _read_with_a_token("openid read")

    assert json_of(answered) == {"sub": USER_IDENTIFIER}


async def test_the_claims_are_answered_to_a_form_posted_to_the_endpoint() -> None:
    async with serving(served_application(openid_kernel(USERINFO_ENV))) as client:
        token = await _owner_token(client, "openid profile email")
        answered = await client.post(
            USERINFO,
            headers={**_bearer(token), "Content-Type": "application/x-www-form-urlencoded"},
            content=b"",
        )

    assert answered.status_code == 200, answered.text
    assert json_of(answered) == ALICES_CLAIMS


async def test_a_token_in_a_posted_form_alone_is_not_read() -> None:
    # The access tokens' authenticator reads the Authorization header only, so
    # a token carried in the form proves nobody and the endpoint fails closed.
    async with serving(served_application(openid_kernel(USERINFO_ENV))) as client:
        token = await _owner_token(client, "openid profile email")
        answered = await client.post(USERINFO, data={"access_token": token})

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_token"


async def test_a_body_that_is_not_a_form_is_refused_as_malformed() -> None:
    async with serving(served_application(openid_kernel(USERINFO_ENV))) as client:
        token = await _owner_token(client, "openid profile email")
        answered = await client.post(USERINFO, headers=_bearer(token), json={"scope": "openid"})

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_request_with_no_token_is_refused_without_revealing_a_claim() -> None:
    # No firewall stands in front of the endpoint in this deployment, so the
    # endpoint alone has to refuse.
    async with serving(served_application(openid_kernel(IDENTITY_PROVIDER_ENV))) as client:
        answered = await client.get(USERINFO)

    assert answered.status_code == 401
    document = json_of(answered)
    assert set(document) == {"error", "error_description"}
    assert document["error"] == "invalid_token"
    assert answered.headers["www-authenticate"].startswith('Bearer error="invalid_token"')


async def test_a_token_a_client_was_issued_for_itself_is_refused() -> None:
    # It carries openid, but no end-user signed in: there is nobody to describe.
    async with serving(served_application(openid_kernel(USERINFO_ENV))) as client:
        token = await _service_token(client, "openid")
        answered = await client.get(USERINFO, headers=_bearer(token))

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_token"


async def test_a_token_not_granted_openid_is_refused_as_insufficient() -> None:
    answered = await _read_with_a_token("profile email")

    assert answered.status_code == 403
    assert text_field(json_of(answered), "error") == "insufficient_scope"
    assert 'scope="openid"' in answered.headers["www-authenticate"]


async def test_a_deployment_naming_no_identity_provider_boots() -> None:
    async with serving(served_application(openid_kernel())) as client:
        answered = await client.get("/.well-known/oauth-authorization-server")

    assert answered.status_code == 200


async def test_reading_claims_with_no_identity_provider_names_the_setting() -> None:
    # The refusal reaches whoever runs the application, not the client.
    async with serving(served_application(openid_kernel())) as client:
        with pytest.raises(InvalidConfigurationError) as raised:
            _ = await client.get(USERINFO)

    assert "identity_provider" in str(raised.value)
    assert "config/packages/openid_connect_server.py" in str(raised.value)
