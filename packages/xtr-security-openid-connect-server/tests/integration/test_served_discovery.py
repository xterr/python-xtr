"""The OpenID configuration document, served for real and read by the relying party.

Each test serves the fixture deployment and hands what it answered to the
repository's own relying party, which reads the document the way a client
discovering the provider does: from the issuer's well-known path, checking
the issuer it announces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest
from xtr_security_oauth2_server.exception import (
    InvalidConfigurationError as OAuth2InvalidConfigurationError,
)

from tests.fixtures.openid_app.config import (
    DISCOVERY_ALGORITHM,
    DISCOVERY_ENV,
    IDENTITY_PROVIDER_ENV,
    NO_SCOPES_ENV,
)
from tests.support.relying_party import CONFIGURATION_PATH, relying_party_of
from tests.support.served import json_of, openid_kernel, served_application, serving
from tests.support.signing import ISSUER

if TYPE_CHECKING:
    from tests.support.relying_party import RelyingParty

pytestmark = pytest.mark.anyio

#: The routes file moving the provider's userinfo endpoint under ``/oidc``.
UNDER_OIDC: Final = "tests.fixtures.openid_routes_under_oidc"

#: What the ID token itself claims, beside the claims of the protocol's four
#: scopes — of which ``profile`` and ``address`` are claims too, and ``phone``
#: is not.
CLAIMS_SUPPORTED: Final = sorted(
    {
        "sub",
        "iss",
        "aud",
        "exp",
        "iat",
        "auth_time",
        "nonce",
        "name",
        "family_name",
        "given_name",
        "middle_name",
        "nickname",
        "preferred_username",
        "profile",
        "picture",
        "website",
        "gender",
        "birthdate",
        "zoneinfo",
        "locale",
        "updated_at",
        "email",
        "email_verified",
        "address",
        "phone_number",
        "phone_number_verified",
    },
)

#: The fields this provider adds to the authorization server's description.
OPENID_FIELDS: Final = (
    "userinfo_endpoint",
    "subject_types_supported",
    "id_token_signing_alg_values_supported",
    "claims_supported",
    "claims_parameter_supported",
    "request_parameter_supported",
    "request_uri_parameter_supported",
)


async def _discovered(env: str = DISCOVERY_ENV, routes_module: str | None = None) -> RelyingParty:
    """Serve the deployment in ``env`` and return the relying party over what it answered."""
    app = served_application(openid_kernel(env, routes_module=routes_module))
    async with serving(app) as client:
        return await relying_party_of(client, DISCOVERY_ALGORITHM)


async def test_the_relying_party_discovers_the_provider_at_its_issuer() -> None:
    discovery = (await _discovered()).discovery

    assert await discovery.get_issuer() == ISSUER


async def test_the_userinfo_endpoint_is_published_under_the_issuer() -> None:
    discovery = (await _discovered()).discovery

    assert await discovery.get_secure_endpoint("userinfo_endpoint") == f"{ISSUER}/userinfo"


async def test_the_authorization_server_endpoints_are_published_beside_it() -> None:
    discovery = (await _discovered()).discovery

    assert await discovery.get_secure_endpoint("authorization_endpoint") == f"{ISSUER}/authorize"
    assert await discovery.get_secure_endpoint("token_endpoint") == f"{ISSUER}/token"
    assert await discovery.get_secure_endpoint("jwks_uri") == f"{ISSUER}/.well-known/jwks.json"


async def test_only_public_subject_identifiers_are_published() -> None:
    document = await (await _discovered()).discovery.get_configuration()

    assert document["subject_types_supported"] == ["public"]


async def test_id_tokens_are_published_signed_with_the_servers_algorithm() -> None:
    document = await (await _discovered()).discovery.get_configuration()

    assert document["id_token_signing_alg_values_supported"] == [DISCOVERY_ALGORITHM]
    assert document["id_token_signing_alg_values_supported"] == ["RS256"]


async def test_the_authorization_code_is_the_only_response_type() -> None:
    document = await (await _discovered()).discovery.get_configuration()

    assert document["response_types_supported"] == ["code"]


async def test_the_request_parameters_the_provider_ignores_are_published_unsupported() -> None:
    document = await (await _discovered()).discovery.get_configuration()

    assert document["claims_parameter_supported"] is False
    assert document["request_parameter_supported"] is False
    assert document["request_uri_parameter_supported"] is False


async def test_every_claim_the_provider_can_reveal_is_published_and_no_scope_name() -> None:
    document = await (await _discovered()).discovery.get_configuration()

    assert document["claims_supported"] == CLAIMS_SUPPORTED


async def test_a_claim_set_of_the_deployments_own_publishes_its_claims_not_its_scope() -> None:
    document = await (await _discovered(IDENTITY_PROVIDER_ENV)).discovery.get_configuration()

    supported = document["claims_supported"]
    assert isinstance(supported, list)
    assert "company_id" in supported
    assert "company" not in supported


async def test_a_moved_userinfo_endpoint_is_published_where_it_now_is() -> None:
    discovery = (await _discovered(routes_module=UNDER_OIDC)).discovery

    endpoint = await discovery.get_secure_endpoint("userinfo_endpoint")
    assert endpoint == f"{ISSUER}/oidc/userinfo"
    assert endpoint.endswith("/oidc/userinfo")


async def test_the_document_stays_at_the_root_when_the_userinfo_endpoint_moves() -> None:
    app = served_application(openid_kernel(DISCOVERY_ENV, routes_module=UNDER_OIDC))
    async with serving(app) as client:
        moved = await client.get("/oidc/.well-known/openid-configuration")
        answered = await client.get(CONFIGURATION_PATH)

    assert moved.status_code == 404
    assert answered.status_code == 200


async def test_the_answer_is_a_json_document() -> None:
    async with serving(served_application(openid_kernel(DISCOVERY_ENV))) as client:
        answered = await client.get(CONFIGURATION_PATH)

    assert answered.status_code == 200
    assert answered.headers["content-type"] == "application/json"


async def test_the_authorization_servers_description_carries_the_same_fields() -> None:
    async with serving(served_application(openid_kernel(DISCOVERY_ENV))) as client:
        openid = json_of(await client.get(CONFIGURATION_PATH))
        oauth2 = json_of(await client.get("/.well-known/oauth-authorization-server"))

    assert {name: oauth2[name] for name in OPENID_FIELDS} == {
        name: openid[name] for name in OPENID_FIELDS
    }
    assert oauth2 == openid


async def test_a_deployment_naming_no_scope_is_told_so_when_the_document_is_asked_for() -> None:
    # The refusal reaches whoever runs the application, not the client.
    async with serving(served_application(openid_kernel(NO_SCOPES_ENV))) as client:
        with pytest.raises(OAuth2InvalidConfigurationError) as raised:
            _ = await client.get(CONFIGURATION_PATH)

    assert "scopes.available" in str(raised.value)
