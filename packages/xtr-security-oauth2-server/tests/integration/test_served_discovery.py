"""What this server publishes about itself, served through a real application."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from tests.support.served import (
    client_credentials_token,
    header_of,
    json_of,
    served_application,
    serving,
    text_field,
    text_fields,
)
from tests.support.signing import ISSUER

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio

METADATA_PATH = "/.well-known/oauth-authorization-server"
JWKS_PATH = "/.well-known/jwks.json"


def _published_keys(document: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Return the keys a published set holds."""
    keys = document["keys"]
    assert isinstance(keys, list), f"keys is {keys!r}, not a list"

    return cast("list[Mapping[str, object]]", keys)


async def test_the_description_names_this_server_by_its_issuer() -> None:
    async with serving(served_application()) as client:
        answered = await client.get(METADATA_PATH)

    assert answered.status_code == 200
    assert text_field(json_of(answered), "issuer") == ISSUER


async def test_every_endpoint_the_deployment_serves_is_named_under_the_issuer() -> None:
    async with serving(served_application()) as client:
        document = json_of(await client.get(METADATA_PATH))

    assert text_field(document, "authorization_endpoint") == f"{ISSUER}/authorize"
    assert text_field(document, "token_endpoint") == f"{ISSUER}/token"
    assert text_field(document, "jwks_uri") == f"{ISSUER}/.well-known/jwks.json"
    assert text_field(document, "revocation_endpoint") == f"{ISSUER}/revoke"
    assert text_field(document, "introspection_endpoint") == f"{ISSUER}/introspect"
    assert text_field(document, "device_authorization_endpoint") == f"{ISSUER}/device-code"


async def test_the_description_names_the_scopes_and_the_flows_that_run() -> None:
    async with serving(served_application()) as client:
        document = json_of(await client.get(METADATA_PATH))

    assert text_fields(document, "scopes_supported") == ["read", "write"]
    assert set(text_fields(document, "grant_types_supported")) == {
        "authorization_code",
        "client_credentials",
        "refresh_token",
        "urn:ietf:params:oauth:grant-type:device_code",
        "password",
        "implicit",
    }


async def test_the_description_names_the_authorization_responses_the_flows_ask_for() -> None:
    async with serving(served_application()) as client:
        document = json_of(await client.get(METADATA_PATH))

    assert set(text_fields(document, "response_types_supported")) == {"code", "token"}


async def test_the_description_names_how_a_proof_key_may_be_derived() -> None:
    async with serving(served_application()) as client:
        document = json_of(await client.get(METADATA_PATH))

    assert text_fields(document, "code_challenge_methods_supported") == ["S256", "plain"]


async def test_the_description_names_how_a_client_may_authenticate() -> None:
    async with serving(served_application()) as client:
        document = json_of(await client.get(METADATA_PATH))

    for field in (
        "token_endpoint_auth_methods_supported",
        "revocation_endpoint_auth_methods_supported",
        "introspection_endpoint_auth_methods_supported",
    ):
        assert text_fields(document, field) == [
            "client_secret_basic",
            "client_secret_post",
            "none",
        ]


async def test_the_published_key_set_holds_only_public_halves() -> None:
    async with serving(served_application()) as client:
        answered = await client.get(JWKS_PATH)

    assert answered.status_code == 200
    assert answered.headers["content-type"].startswith("application/jwk-set+json")
    keys = _published_keys(json_of(answered))
    assert keys
    for key in keys:
        assert text_field(key, "kty") == "RSA"
        # The private exponent would make the whole pair readable.
        assert "d" not in key


async def test_the_published_key_names_the_one_our_tokens_are_signed_with() -> None:
    # A signer stamping a kid and a verifier reading the published set must
    # agree on the id with nothing passed between them.
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        published = json_of(await client.get(JWKS_PATH))

    named = {text_field(key, "kid") for key in _published_keys(published)}

    assert text_field(header_of(token), "kid") in named


async def test_an_access_token_announces_the_profile_it_follows() -> None:
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)

    assert text_field(header_of(token), "typ") == "at+jwt"
