"""RFC 8414 — OAuth 2.0 Authorization Server Metadata.

Cases ported from oauthlib 4.0.0 (145a9a4), whose ``MetadataEndpointTest``
fixes which fields are mandatory and that the issuer is validated. Everything
here is read off a served document, since the requirements are about what a
client finds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI

from tests.support.served import (
    json_of,
    oauth2_kernel,
    served_application,
    serving,
    text_field,
    text_fields,
)
from tests.support.signing import ISSUER
from xtr_security_oauth2_server._endpoint_paths import (
    JWKS_PATH,
    METADATA_FIELDS,
    METADATA_PATH,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio

#: Every deployment-dependent field whose value is a URL under the issuer.
ENDPOINT_FIELDS: Final = tuple(METADATA_FIELDS)


def _application() -> FastAPI:
    """Return a deployment with every endpoint this server ships turned on."""
    return served_application(oauth2_kernel("tests.fixtures.oauth2_conformance_app"))


async def _document() -> Mapping[str, object]:
    """Return the description this server publishes about itself."""
    async with serving(_application()) as client:
        answered = await client.get(METADATA_PATH)

    assert answered.status_code == 200, answered.text

    return json_of(answered)


# Section 2 — Authorization Server Metadata


async def test_the_description_names_the_issuer() -> None:
    # "issuer — REQUIRED. The authorization server's issuer identifier"
    # (section 2). Ported from oauthlib's ``test_mandatory_fields``.
    assert text_field(await _document(), "issuer") == ISSUER


async def test_the_issuer_carries_no_query_and_no_fragment() -> None:
    # "The issuer identifier is a URL that uses the "https" scheme and has no
    # query or fragment components" (section 2).
    split = urlsplit(text_field(await _document(), "issuer"))

    assert split.query == ""
    assert split.fragment == ""


async def test_the_description_names_the_authorization_and_token_endpoints() -> None:
    # "authorization_endpoint — URL of the authorization server's authorization
    # endpoint", "token_endpoint — URL of the authorization server's token
    # endpoint" (section 2). Ported from oauthlib's ``test_token_endpoint``.
    document = await _document()

    assert text_field(document, "authorization_endpoint") == f"{ISSUER}/authorize"
    assert text_field(document, "token_endpoint") == f"{ISSUER}/token"


async def test_every_endpoint_named_is_an_absolute_url_under_the_issuer() -> None:
    # Each endpoint field of section 2 is a URL, and this server's own
    # endpoints all live under the issuer it publishes.
    document = await _document()

    for field in ENDPOINT_FIELDS:
        named = text_field(document, field)
        assert named.startswith(f"{ISSUER}/"), f"{field} is {named}"
        assert urlsplit(named).scheme != ""


async def test_the_key_set_is_published_over_https() -> None:
    # "jwks_uri — ... This URL MUST use the "https" scheme" (section 2).
    assert urlsplit(text_field(await _document(), "jwks_uri")).scheme == "https"


async def test_the_description_names_the_responses_this_server_issues() -> None:
    # "response_types_supported — REQUIRED. JSON array containing a list of the
    # OAuth 2.0 "response_type" values that this authorization server
    # supports" (section 2). Ported from oauthlib's ``test_mandatory_fields``.
    supported = text_fields(await _document(), "response_types_supported")

    assert "code" in supported
    assert "token" in supported


async def test_the_description_names_the_flows_this_server_runs() -> None:
    # "grant_types_supported — OPTIONAL. JSON array containing a list of the
    # OAuth 2.0 grant type values that this authorization server supports"
    # (section 2).
    supported = text_fields(await _document(), "grant_types_supported")

    assert "authorization_code" in supported
    assert "client_credentials" in supported
    assert "refresh_token" in supported
    assert "password" in supported
    assert "implicit" in supported
    assert "urn:ietf:params:oauth:grant-type:device_code" in supported


async def test_the_description_names_how_a_client_may_authenticate() -> None:
    # "token_endpoint_auth_methods_supported — OPTIONAL. JSON array containing
    # a list of client authentication methods supported by this token
    # endpoint" (section 2).
    supported = text_fields(await _document(), "token_endpoint_auth_methods_supported")

    assert "client_secret_basic" in supported
    assert "client_secret_post" in supported


async def test_the_description_names_the_scopes_a_client_may_ask_for() -> None:
    # "scopes_supported — RECOMMENDED. JSON array containing a list of the
    # OAuth 2.0 "scope" values that this authorization server supports"
    # (section 2).
    supported = text_fields(await _document(), "scopes_supported")

    assert set(supported) == {"read", "write"}


async def test_the_description_names_how_a_proof_key_may_be_derived() -> None:
    # "code_challenge_methods_supported — OPTIONAL. JSON array containing a
    # list of Proof Key for Code Exchange (PKCE) code challenge methods
    # supported by this authorization server" (section 2), which RFC 9700
    # section 2.1 recommends publishing so a client can detect the support.
    supported = text_fields(await _document(), "code_challenge_methods_supported")

    assert "S256" in supported


# Section 3 — Obtaining Authorization Server Metadata


async def test_the_description_lives_at_the_well_known_path() -> None:
    # "Authorization servers supporting metadata MUST make a JSON document
    # containing metadata as specified in Section 2 available at a path formed
    # by inserting a well-known URI string into the authorization server's
    # issuer identifier between the host component and the path component, if
    # any. By default, the well-known URI string used is
    # "/.well-known/oauth-authorization-server"" (section 3).
    assert METADATA_PATH == "/.well-known/oauth-authorization-server"
    async with serving(_application()) as client:
        answered = await client.get(METADATA_PATH)

    assert answered.status_code == 200


# Section 3.1 / 3.2 — Request and response


async def test_the_description_is_read_with_a_get() -> None:
    # "An authorization server metadata document MUST be queried using an HTTP
    # "GET" request at the previously specified path" (section 3.1).
    async with serving(_application()) as client:
        answered = await client.get(METADATA_PATH)
        posted = await client.post(METADATA_PATH)

    assert answered.status_code == 200
    # Whatever a POST is answered with, it is not the document.
    assert posted.status_code != 200


async def test_a_successful_answer_is_two_hundred_and_json() -> None:
    # "A successful response MUST use the 200 OK HTTP status code and return a
    # JSON object using the "application/json" content type" (section 3.2).
    async with serving(_application()) as client:
        answered = await client.get(METADATA_PATH)

    assert answered.status_code == 200
    assert answered.headers["content-type"].startswith("application/json")


async def test_a_field_with_nothing_in_it_is_left_out() -> None:
    # "Claims with zero elements MUST be omitted from the response" (section
    # 3.2). This deployment configures no audience and contributes no extra
    # field, and the document names nothing empty.
    document = await _document()

    for name, value in document.items():
        assert value != [], f"{name} is published as an empty list"
        assert value != "", f"{name} is published as an empty string"
        assert value != {}, f"{name} is published as an empty object"


# Section 3.3 — Authorization Server Metadata Validation


async def test_the_issuer_published_is_the_one_the_document_was_read_under() -> None:
    # "The "issuer" value returned MUST be identical to the authorization
    # server's issuer identifier value into which the well-known URI string was
    # inserted to create the URL used to retrieve the metadata" (section 3.3).
    # Ported from oauthlib's ``test_metadata_validate_issuer``.
    document = await _document()
    published = text_field(document, "issuer")

    assert published == ISSUER
    # Read the other way: the document really is under that issuer, with the
    # well-known string inserted and nothing else.
    assert f"{published}{METADATA_PATH}" == f"{ISSUER}/.well-known/oauth-authorization-server"


# The published key set


async def test_the_key_set_is_served_where_the_description_says() -> None:
    # The ``jwks_uri`` of section 2 has to be a URL that answers; a document
    # naming a path nothing serves is worse than no document.
    async with serving(_application()) as client:
        document = json_of(await client.get(METADATA_PATH))
        named = text_field(document, "jwks_uri")
        answered = await client.get(urlsplit(named).path)

    assert urlsplit(named).path == JWKS_PATH
    assert answered.status_code == 200
    published = json_of(answered)
    assert isinstance(published["keys"], list)
