"""OpenID Connect Discovery 1.0 — the provider's configuration document.

The document is fetched from the served deployment and read as a client
discovering the provider reads it: through the repository's own discovery
reader, which refuses a document whose issuer is not the one it was read
under and an endpoint that is not HTTPS. The deployment signs with RS256,
named explicitly, as Section 3 asks every provider to support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast
from urllib.parse import urlsplit

import pytest

from tests.fixtures.openid_app.config import DISCOVERY_ALGORITHM, DISCOVERY_ENV
from tests.support.relying_party import CONFIGURATION_PATH, relying_party_of
from tests.support.served import json_of, openid_kernel, served_application, serving, text_field
from tests.support.signing import ISSUER

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

pytestmark = pytest.mark.anyio

#: What a JWK carries only when it holds a private or a symmetric key.
_SECRET_MEMBERS: Final = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth", "k"})


async def _served(path: str) -> httpx.Response:
    """Return what the deployment answers a GET of ``path`` with."""
    async with serving(served_application(openid_kernel(DISCOVERY_ENV))) as client:
        return await client.get(path)


async def _document() -> Mapping[str, object]:
    """Return the configuration document, as the relying party read and accepted it."""
    async with serving(served_application(openid_kernel(DISCOVERY_ENV))) as client:
        relying_party = await relying_party_of(client, DISCOVERY_ALGORITHM)

    return await relying_party.discovery.get_configuration()


# Section 4 — Obtaining OpenID Provider Configuration Information


async def test_the_document_is_served_under_the_issuer_at_the_well_known_path() -> None:
    # "OpenID Providers supporting Discovery MUST make a JSON document
    # available at the path formed by concatenating the string
    # /.well-known/openid-configuration to the Issuer."
    answered = await _served(CONFIGURATION_PATH)

    assert answered.status_code == 200
    assert f"{text_field(json_of(answered), 'issuer')}{CONFIGURATION_PATH}" == (
        f"{ISSUER}/.well-known/openid-configuration"
    )


# Section 4.2 — OpenID Provider Configuration Response


async def test_a_successful_answer_is_two_hundred_and_json() -> None:
    # "A successful response MUST use the 200 OK HTTP status code and return a
    # JSON object using the application/json content type."
    answered = await _served(CONFIGURATION_PATH)

    assert answered.status_code == 200
    assert answered.headers["content-type"] == "application/json"
    assert isinstance(answered.json(), dict)


async def test_a_field_with_nothing_in_it_is_left_out() -> None:
    # "Claims with zero elements MUST be omitted from the response."
    document = await _document()

    for name, value in document.items():
        assert value not in ([], "", {}), f"{name} is published empty"


# Section 4.3 — OpenID Provider Configuration Validation


async def test_the_issuer_published_is_the_one_the_document_was_read_under() -> None:
    # "The issuer value returned MUST be identical to the Issuer URL that was
    # used as the prefix to /.well-known/openid-configuration." The reader
    # refuses the document otherwise.
    async with serving(served_application(openid_kernel(DISCOVERY_ENV))) as client:
        relying_party = await relying_party_of(client, DISCOVERY_ALGORITHM)

    assert await relying_party.discovery.get_issuer() == ISSUER


# Section 3 — OpenID Provider Metadata


async def test_the_issuer_is_an_https_url_with_no_query_and_no_fragment() -> None:
    issuer = urlsplit(text_field(await _document(), "issuer"))

    assert issuer.scheme == "https"
    assert (issuer.query, issuer.fragment) == ("", "")


async def test_every_required_field_is_published() -> None:
    document = await _document()

    assert {
        "issuer",
        "authorization_endpoint",
        "token_endpoint",
        "jwks_uri",
        "response_types_supported",
        "subject_types_supported",
        "id_token_signing_alg_values_supported",
    } <= set(document)


async def test_the_endpoints_are_https_urls_under_the_issuer() -> None:
    # "userinfo_endpoint ... This URL MUST use the https scheme", as every
    # endpoint here does; the reader refuses one that does not.
    async with serving(served_application(openid_kernel(DISCOVERY_ENV))) as client:
        discovery = (await relying_party_of(client, DISCOVERY_ALGORITHM)).discovery

    for field in ("authorization_endpoint", "token_endpoint", "userinfo_endpoint", "jwks_uri"):
        assert (await discovery.get_secure_endpoint(field)).startswith(f"{ISSUER}/")


async def test_rs256_is_among_the_id_token_signing_algorithms() -> None:
    # "id_token_signing_alg_values_supported ... The algorithm RS256 MUST be
    # included."
    assert "RS256" in cast(
        "list[str]", (await _document())["id_token_signing_alg_values_supported"]
    )


async def test_the_openid_scope_is_supported() -> None:
    # "scopes_supported ... The server MUST support the openid scope value."
    assert "openid" in cast("list[str]", (await _document())["scopes_supported"])


async def test_the_code_flow_is_the_response_type_published() -> None:
    assert (await _document())["response_types_supported"] == ["code"]


async def test_public_subject_identifiers_are_published() -> None:
    # "Valid types include pairwise and public."
    assert (await _document())["subject_types_supported"] == ["public"]


async def test_the_parameters_the_provider_does_not_read_are_published_unsupported() -> None:
    document = await _document()

    assert document["claims_parameter_supported"] is False
    assert document["request_parameter_supported"] is False
    assert document["request_uri_parameter_supported"] is False


async def test_the_claims_published_include_every_claim_an_id_token_carries() -> None:
    supported = cast("list[str]", (await _document())["claims_supported"])

    assert {"sub", "iss", "aud", "exp", "iat", "auth_time", "nonce"} <= set(supported)


# Section 3 — jwks_uri


async def test_the_key_set_holds_no_private_or_symmetric_key() -> None:
    # "The JWK Set MUST NOT contain private or symmetric key values."
    keys = cast(
        "list[Mapping[str, object]]", json_of(await _served("/.well-known/jwks.json"))["keys"]
    )

    assert keys
    assert all(_SECRET_MEMBERS.isdisjoint(key) for key in keys)


async def test_every_published_key_names_its_use() -> None:
    # "When both signing and encryption keys are made available, a use (Key
    # Use) parameter value is REQUIRED for all keys": every key here says it
    # is for signatures.
    keys = cast(
        "list[Mapping[str, object]]", json_of(await _served("/.well-known/jwks.json"))["keys"]
    )

    assert {key["use"] for key in keys} == {"sig"}
