"""An ordinary deployment, which happens to have an add-on listed beside it.

Nothing here names the add-on's grant, its answer or its contribution: the
bundle next to this prepends what it replaces and registers what it adds, which
is the whole of what an add-on does to a deployment that knows nothing about
it. The settings below are an ordinary deployment's — the lifetimes, the
proof-key requirement, the scopes — and what the add-on contributes has to
honour them.

``enable_auth_code_grant`` is deliberately left unsaid: the add-on turns the
shipped redirect flow off and registers its own, and a deployment naming it
here would be answering a question the add-on answers.

The proof-key requirement is the one setting that differs between the two
environments this deployment is served in: ``open_proof_key`` turns it off, so
the pair of answers a public client meets — a refusal in one, a code in the
other — says which value reached the add-on's grant.

The resource owner is established on ``/authorize`` by this deployment's own
access tokens, as the redirect-flow deployment beside it does, and the add-on's
own route is read by them too.
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

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.signing import ALGORITHM, ISSUER, SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2AuthenticatorConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = [
    "AUTH_CODE_TTL",
    "OPEN_PROOF_KEY_ENV",
    "PROTECTED",
    "REFRESH_TOKEN_TTL",
    "USER_IDENTIFIER",
    "USER_PASSWORD",
    "USER_ROLES",
    "oauth2_server",
    "security",
    "without_the_proof_key_requirement",
]

#: How long this deployment's authorization codes last. Not the shipped default
#: of ten minutes, so that a code the add-on's grant issues for this long is
#: proof the grant was built with what the deployment configured rather than
#: with what the grant would have chosen.
AUTH_CODE_TTL: Final[timedelta] = timedelta(minutes=7)

#: How long this deployment's refresh tokens last. Not the shipped default of
#: thirty days, for the same reason: a refresh token the add-on's grant hands
#: out lasting nine says the lifetime reached the grant from here.
REFRESH_TOKEN_TTL: Final[timedelta] = timedelta(days=9)

#: The environment this deployment is served in when a client holding no secret
#: may start the flow without a proof key. One deployment in two environments
#: rather than two deployments: the requirement is the only setting that
#: differs, so what a public client meets in each — a code or a refusal — can
#: only be the setting the add-on's grant was built with.
OPEN_PROOF_KEY_ENV: Final[str] = "open_proof_key"

#: The resource owner who approves, and the credential that establishes them.
USER_IDENTIFIER: Final[str] = "ada"
USER_PASSWORD: Final[str] = "the-resource-owners-password"
USER_ROLES: Final[tuple[str, ...]] = ("ROLE_USER",)

#: What the firewall claims: the authorization endpoint, where a person is, and
#: the add-on's own route. Never the token endpoint — authenticating the client
#: there is the authorization server's own job.
PROTECTED: Final[str] = r"^/(authorize|userinfo)"


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Run the password flow that establishes the owner, and nothing else shipped.

    The key is a minted one rather than a password, so a test can read back
    what a code the add-on's grant sealed carries.
    """
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            private_key=SIGNING_KEY_PEM,
            encryption_key=ENCRYPTION_KEY,
            encryption_key_type="key",
            issuer=ISSUER,
            signature_algorithm=ALGORITHM,
            auth_code_ttl=AUTH_CODE_TTL,
            refresh_token_ttl=REFRESH_TOKEN_TTL,
            enable_password_grant=True,
            enable_device_code_grant=False,
            # Named here because the add-on's grant has to honour it, and the
            # refusal a public client meets in this environment — against the
            # code it is handed in the one below — is what proves it does.
            require_code_challenge_for_public_clients=True,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )


@configure
@when(OPEN_PROOF_KEY_ENV)
def without_the_proof_key_requirement(config: OAuth2ServerConfig) -> OAuth2ServerConfig:
    """Let a client holding no secret start the flow with no proof key.

    What a deployment with native clients too old to send one would say. The
    add-on's grant is handed this setting the same way it is handed the
    lifetimes, so turning it off here is the only thing that can account for a
    public client being issued a code.
    """
    return replace(
        config,
        authorization_server=replace(
            config.authorization_server,
            require_code_challenge_for_public_clients=False,
        ),
    )


@configure
def security() -> SecurityConfig:
    """Establish the resource owner on ``/authorize`` and the caller on the add-on's route."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={USER_IDENTIFIER: {"roles": list(USER_ROLES)}},
            ),
        },
        firewalls={
            "api": FirewallConfig(
                pattern=PROTECTED,
                provider="users",
                authenticators=(OAuth2AuthenticatorConfig(),),
            ),
        },
        access_control=(AccessControlConfig(path=PROTECTED, attribute="IS_AUTHENTICATED"),),
    )
