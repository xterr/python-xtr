"""The OIDC login configuration: an authorization-code login, described as inert data.

One authenticator ships here — the OIDC authorization-code login — with the
token generator the token-generate command mints through. Both live behind
xtr-security-http's ``oidc`` extra; the bundle registers their factory only
when that extra is installed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence  # noqa: TC003 -- field types read at runtime
from dataclasses import dataclass, field
from typing import Literal

from xtr_security.exception import InvalidConfigurationError

__all__ = [
    "OidcLoginConfig",
    "OidcTokenGeneratorConfig",
    "TokenEndpointAuthMethod",
]

TokenEndpointAuthMethod = Literal[
    "none",
    "client_secret_basic",
    "client_secret_post",
    "client_secret_jwt",
    "private_key_jwt",
    "tls_client_auth",
    "self_signed_tls_client_auth",
]
"""How the client authenticates at the provider's token endpoint."""

_KNOWN_METHODS = frozenset(
    (
        "none",
        "client_secret_basic",
        "client_secret_post",
        "client_secret_jwt",
        "private_key_jwt",
        "tls_client_auth",
        "self_signed_tls_client_auth",
    )
)

_METHODS_WITHOUT_SECRET = frozenset(("none", "tls_client_auth", "self_signed_tls_client_auth"))

_KNOWN_PKCE_METHODS = frozenset(("S256", "plain"))

_KNOWN_USER_DATA_SOURCES = frozenset(("userinfo", "id_token"))


@dataclass(frozen=True, slots=True)
class OidcTokenGeneratorConfig:
    """The tokens the token-generate command mints for one firewall.

    Attributes:
        algorithms: The signature algorithms a minted token may be signed with.
        keyset: A JWKS document carrying the signing keys.
        audience: The audience a minted token names — one or several.
        issuers: The issuers a minted token may be issued by; exactly one when
            the mint does not name one.
        claim: The claim the user identifier is written to.

    Raises:
        InvalidConfigurationError: When no algorithm, key set, audience or
            issuer is given.
    """

    algorithms: Sequence[str]
    keyset: str
    audience: str | Sequence[str]
    issuers: Sequence[str]
    claim: str = "sub"

    def __post_init__(self) -> None:
        """Check the signing keys, the audience and the issuers are there."""
        if not self.algorithms:
            raise InvalidConfigurationError(
                "An OIDC token generator needs at least one signature algorithm.",
            )
        if not self.keyset:
            raise InvalidConfigurationError("An OIDC token generator needs its signing keys.")
        if not self.audience:
            raise InvalidConfigurationError("An OIDC token generator needs an audience.")
        if not self.issuers:
            raise InvalidConfigurationError(
                "An OIDC token generator needs at least one issuer.",
            )


def _no_authorization_params() -> dict[str, str]:
    """The empty authorization-parameter mapping a login configuration starts with."""
    return {}


@dataclass(frozen=True, slots=True)
class OidcLoginConfig:
    """An OIDC authorization-code login: the provider redirects, the callback authenticates.

    The provider is discovered from the ``issuer`` — its endpoints read off the
    well-known document — and the client authenticates at its token endpoint
    by ``token_endpoint_auth_method``. The login answers on ``check_path``.

    Attributes:
        issuer: The provider's issuer URI, the base its discovery document is
            read from.
        client_id: The client the provider knows this application by.
        client_secret: The client's secret, for the secret-bearing endpoint
            authentication methods; ``None`` for the public and TLS ones.
        token_endpoint_auth_method: How the client authenticates at the
            provider's token endpoint.
        scope: The scopes asked of the provider, space-separated; ``openid``
            is always asked beside them.
        check_path: The path the provider redirects the login back to.
        pkce_enabled: Whether the login proves its code with a PKCE verifier.
        pkce_method: The PKCE challenge method, ``"S256"`` or ``"plain"``.
        user_data_source: Where the user is read from — the userinfo endpoint
            or the ID token's claims.
        user_identifier_claim: The claim naming the user.
        max_age: The oldest authentication the login accepts, in seconds, or
            ``None`` for no limit.
        authorization_params: Extra query parameters the authorization request
            carries; the login owns the parameters it manages.
        signature_verifier_algorithms: The algorithms the ID token's signature
            is verified against, or ``None`` to read the token without
            verifying its signature.
        client_authentication_keyset: A JWKS document carrying the private
            key the ``private_key_jwt`` method signs its assertion with.
        certificate_options: The certificate the TLS endpoint authentication
            methods present — ``local_cert``, ``local_pk`` and
            ``passphrase`` — carried on the client.
        token_generator: The tokens the token-generate command mints for this
            firewall, or ``None`` when it mints none.

    Raises:
        InvalidConfigurationError: When the issuer or client is missing, when
            a secret-bearing method has no secret or a public one does, or
            when the PKCE method or the user-data source is unknown.
    """

    issuer: str
    client_id: str
    client_secret: str | None = None
    token_endpoint_auth_method: TokenEndpointAuthMethod = "client_secret_basic"  # noqa: S105 -- a method name, not a secret
    scope: str = "openid"
    check_path: str = "/oidc/callback"
    pkce_enabled: bool = True
    pkce_method: str = "S256"
    user_data_source: str = "userinfo"
    user_identifier_claim: str = "sub"
    max_age: int | None = None
    authorization_params: Mapping[str, str] = field(default_factory=_no_authorization_params)
    signature_verifier_algorithms: Sequence[str] | None = None
    client_authentication_keyset: str | None = None
    certificate_options: Mapping[str, str] | None = None
    token_generator: OidcTokenGeneratorConfig | None = None

    def __post_init__(self) -> None:
        """Check the client, its secret and the login's choices."""
        if not self.issuer:
            raise InvalidConfigurationError("An OIDC login needs the provider's issuer.")
        if not self.client_id:
            raise InvalidConfigurationError("An OIDC login needs its client id.")
        if self.token_endpoint_auth_method not in _KNOWN_METHODS:
            raise InvalidConfigurationError(
                f"Unknown token endpoint authentication method "
                f"{self.token_endpoint_auth_method!r}; known are {sorted(_KNOWN_METHODS)}.",
            )
        if self.token_endpoint_auth_method in _METHODS_WITHOUT_SECRET:
            if self.client_secret is not None:
                raise InvalidConfigurationError(
                    f"The token endpoint authentication method "
                    f"{self.token_endpoint_auth_method!r} sends no client secret; "
                    f"set client_secret only with a secret-bearing method.",
                )
        elif self.client_secret is None:
            raise InvalidConfigurationError(
                f"The token endpoint authentication method "
                f"{self.token_endpoint_auth_method!r} needs the client secret.",
            )
        if self.token_endpoint_auth_method == "private_key_jwt" and (  # noqa: S105 -- a method name
            self.client_authentication_keyset is None
        ):
            raise InvalidConfigurationError(
                "The private_key_jwt token endpoint authentication method needs its "
                "signing key; set client_authentication_keyset.",
            )
        if self.pkce_enabled and self.pkce_method not in _KNOWN_PKCE_METHODS:
            raise InvalidConfigurationError(
                f"Unknown PKCE method {self.pkce_method!r}; "
                f"known are {sorted(_KNOWN_PKCE_METHODS)}.",
            )
        if self.user_data_source not in _KNOWN_USER_DATA_SOURCES:
            raise InvalidConfigurationError(
                f"Unknown user data source {self.user_data_source!r}; "
                f"known are {sorted(_KNOWN_USER_DATA_SOURCES)}.",
            )
