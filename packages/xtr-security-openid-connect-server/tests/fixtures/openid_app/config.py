"""An ordinary deployment, and the one setting each of its environments changes.

The base configuration says nothing of the provider: the response type, the
redirect flow and the ``openid`` scope are the provider bundle's to put in
place. The environments below are what an application could write on top, each
named for what it changes, so a test serves exactly the deployment it is about.

The resource owner is established on ``/authorize`` by this deployment's own
access tokens, minted with the password flow: the cheapest arrangement that
still has a real signed-in user reach the consent event.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Final

from xtr_dependency_injection import configure, when
from xtr_security.bundle import (
    AccessControlConfig,
    FirewallConfig,
    InMemoryUserProviderConfig,
    SecurityConfig,
)
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2AuthenticatorConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)
from xtr_security_oauth2_server_core.response_types.bearer_token_response import BearerTokenResponse

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.identity_provider import InMemoryIdentityProvider
from tests.support.signing import ISSUER, signing_key
from xtr_security_openid_connect_server.bundle import OpenIdConnectServerConfig

__all__ = [
    "ALGORITHM",
    "AUTH_CODE_BACK_ON_ENV",
    "BEARER_ANSWER_ENV",
    "IDENTITY_PROVIDER_ENV",
    "ID_TOKEN_TTL",
    "NO_METADATA_ENV",
    "NO_SCOPES_ENV",
    "OPEN_PROOF_KEY_ENV",
    "SHORT_ID_TOKEN_ENV",
    "USER_IDENTIFIER",
    "USER_PASSWORD",
    "oauth2_server",
    "oauth2_server_without_scopes",
    "openid_connect_server_with_identity_provider",
    "openid_connect_server_with_short_id_tokens",
    "security",
    "with_the_bearer_answer_back",
    "with_the_redirect_flow_back_on",
    "without_metadata",
    "without_the_proof_key_requirement",
]

#: What this deployment signs with. Not the server's default ``RS256``, so an ID
#: token whose header says ``ES256`` can only have read it from here.
ALGORITHM: Final[str] = "ES256"

#: How long an ID token lasts where the deployment sets it.
ID_TOKEN_TTL: Final[timedelta] = timedelta(minutes=5)

#: The resource owner who signs in, and the credential that establishes them.
USER_IDENTIFIER: Final[str] = "alice"
USER_PASSWORD: Final[str] = "alices-password"

#: The environments, each named for the one setting it changes.
OPEN_PROOF_KEY_ENV: Final[str] = "open_proof_key"
SHORT_ID_TOKEN_ENV: Final[str] = "short_id_token"
IDENTITY_PROVIDER_ENV: Final[str] = "identity_provider"
AUTH_CODE_BACK_ON_ENV: Final[str] = "auth_code_back_on"
BEARER_ANSWER_ENV: Final[str] = "bearer_answer"
NO_METADATA_ENV: Final[str] = "no_metadata"
NO_SCOPES_ENV: Final[str] = "no_scopes"

#: What the firewall claims: the authorization endpoint, where a person is.
_PROTECTED: Final[str] = r"^/authorize"


def _described(scopes: ScopesConfig) -> OAuth2ServerConfig:
    """Return the deployment, knowing ``scopes``."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=signing_key(ALGORITHM).as_pem(private=True).decode("utf-8"),
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            enable_password_grant=True,
            enable_device_code_grant=False,
        ),
        scopes=scopes,
        persistence=InMemoryPersistenceConfig(),
    )


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Know one scope of the deployment's own; ``openid`` is the provider's to add."""
    return _described(ScopesConfig(available=("read",), default=("read",)))


@configure
@when(NO_SCOPES_ENV)
def oauth2_server_without_scopes() -> OAuth2ServerConfig:
    """Know no scope at all, which the authorization server reports when one is needed."""
    return _described(ScopesConfig())


@configure
@when(OPEN_PROOF_KEY_ENV)
def without_the_proof_key_requirement(config: OAuth2ServerConfig) -> OAuth2ServerConfig:
    """Let a client holding no secret redeem a code with no proof key."""
    return replace(
        config,
        authorization_server=replace(
            config.authorization_server,
            require_code_challenge_for_public_clients=False,
        ),
    )


@configure
@when(AUTH_CODE_BACK_ON_ENV)
def with_the_redirect_flow_back_on(config: OAuth2ServerConfig) -> OAuth2ServerConfig:
    """Turn the shipped redirect flow back on, after the provider turned it off."""
    return replace(
        config,
        authorization_server=replace(config.authorization_server, enable_auth_code_grant=True),
    )


@configure
@when(BEARER_ANSWER_ENV)
def with_the_bearer_answer_back(config: OAuth2ServerConfig) -> OAuth2ServerConfig:
    """Put the plain bearer answer back, after the provider named its own."""
    return replace(
        config,
        authorization_server=replace(
            config.authorization_server,
            response_type_class=BearerTokenResponse,
        ),
    )


@configure
@when(NO_METADATA_ENV)
def without_metadata(config: OAuth2ServerConfig) -> OAuth2ServerConfig:
    """Stop the authorization server describing itself."""
    return replace(
        config,
        authorization_server=replace(config.authorization_server, enable_metadata_endpoint=False),
    )


@configure
@when(SHORT_ID_TOKEN_ENV)
def openid_connect_server_with_short_id_tokens() -> OpenIdConnectServerConfig:
    """Have an ID token last a few minutes rather than as long as its access token."""
    return OpenIdConnectServerConfig(id_token_ttl=ID_TOKEN_TTL)


@configure
@when(IDENTITY_PROVIDER_ENV)
def openid_connect_server_with_identity_provider() -> OpenIdConnectServerConfig:
    """Name where a signed-in user's claims come from, and a scope of the deployment's own."""
    return OpenIdConnectServerConfig(
        identity_provider=InMemoryIdentityProvider,
        claim_sets={"company": ("company_id",)},
    )


@configure
def security() -> SecurityConfig:
    """Establish the resource owner on ``/authorize`` with this server's access tokens."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(users={USER_IDENTIFIER: {"roles": ["ROLE_USER"]}}),
        },
        firewalls={
            "api": FirewallConfig(
                pattern=_PROTECTED,
                provider="users",
                authenticators=(OAuth2AuthenticatorConfig(),),
            ),
        },
        access_control=(AccessControlConfig(path=_PROTECTED, attribute="IS_AUTHENTICATED"),),
    )
