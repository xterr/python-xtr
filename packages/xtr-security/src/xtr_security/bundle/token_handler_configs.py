"""How a bearer access token is validated, described as inert data.

A token handler turns an access-token string into a user badge. Four kinds
ship here — a handler the container provides, one that verifies a
third-party OIDC issuer's tokens, one that introspects a token with its
authorization server, and one that reads the userinfo endpoint — and the
``type`` field tells the kinds apart so a later package adds its own through
the token-handler factory registry (seam S-2).
"""

from __future__ import annotations

import builtins  # noqa: TC003 -- field type read at runtime
from collections.abc import Sequence  # noqa: TC003 -- field type read at runtime
from dataclasses import dataclass, field
from typing import Literal

from xtr_security.exception import InvalidConfigurationError

__all__ = [
    "Oauth2TokenHandlerConfig",
    "OidcTokenHandlerConfig",
    "OidcUserInfoTokenHandlerConfig",
    "ServiceTokenHandlerConfig",
    "TokenHandlerConfig",
]

_MAX_LEEWAY = 300
"""The ceiling, in seconds, on the clock skew an OIDC handler tolerates."""


@dataclass(frozen=True, slots=True)
class ServiceTokenHandlerConfig:
    """An access-token handler the container provides, named by type and qualifier.

    Attributes:
        service: The handler service's type, resolved from the container.
        qualifier: The qualifier that selects between registrations, or ``None``.
        type: The discriminator, always ``"id"``.

    Raises:
        InvalidConfigurationError: When ``service`` is not a class.
    """

    service: builtins.type
    qualifier: str | None = None
    type: Literal["id"] = "id"

    def __post_init__(self) -> None:
        """Check ``service`` is a class, since the container keys services by type."""
        if not isinstance(self.service, type):  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
            raise InvalidConfigurationError(
                f"A service token handler needs a class, not {self.service!r}.",
            )


def _no_issuers() -> Sequence[str]:
    """The empty issuer list an OIDC handler configuration starts with."""
    return ()


def _no_audiences() -> Sequence[str]:
    """The empty audience list an OAuth2 handler configuration starts with."""
    return ()


@dataclass(frozen=True, slots=True)
class OidcTokenHandlerConfig:
    """A handler that verifies a third-party OIDC issuer's access tokens.

    The keys the token is verified against come from exactly one source: a
    ``keyset`` JWKS document pinned in the configuration, a ``discovery_uri`` the
    ``jwks_uri`` is read from, or a ``jwks_uri`` fetched outright. The issuers and
    audience are the ones a valid token must carry.

    Attributes:
        issuers: The issuers a token's ``iss`` must be one of.
        audience: The audience a token's ``aud`` must contain.
        algorithms: The signature algorithms allowed, asymmetric only.
        claim: The claim the user identifier is read from.
        leeway: The clock skew, in seconds, allowed on the time claims — 0 to 300.
        enforce_at_jwt_type: Whether the header's ``typ`` must be ``at+jwt``.
        keyset: A JWKS document pinning the verifying keys, or ``None``.
        discovery_uri: An issuer base URI the ``jwks_uri`` is discovered from, or
            ``None``.
        jwks_uri: The URI the JWKS is fetched from, or ``None``.
        allow_insecure_http: Whether a non-``https`` endpoint is allowed, for a
            development or test issuer.
        type: The discriminator, always ``"oidc"``.

    Raises:
        InvalidConfigurationError: When no issuer is given, or the key source is
            not exactly one of ``keyset``, ``discovery_uri`` or ``jwks_uri``, or
            ``leeway`` is outside 0 to 300 seconds.
    """

    issuers: Sequence[str] = field(default_factory=_no_issuers)
    audience: str = ""
    algorithms: Sequence[str] = ("RS256",)
    claim: str = "sub"
    leeway: int = 0
    enforce_at_jwt_type: bool = False
    keyset: str | None = None
    discovery_uri: str | None = None
    jwks_uri: str | None = None
    allow_insecure_http: bool = False
    type: Literal["oidc"] = "oidc"

    def __post_init__(self) -> None:
        """Check the issuers, the audience and the single key source.

        Raises:
            InvalidConfigurationError: When no issuer or audience is given, or the
                key source is not exactly one, or ``leeway`` is outside 0 to 300.
        """
        if not self.issuers:
            raise InvalidConfigurationError(
                "An OIDC token handler needs at least one trusted issuer.",
            )
        if not self.audience:
            raise InvalidConfigurationError("An OIDC token handler needs an audience.")
        if not 0 <= self.leeway <= _MAX_LEEWAY:
            raise InvalidConfigurationError(
                f"The leeway must be between 0 and {_MAX_LEEWAY} seconds, not {self.leeway}.",
            )
        sources = [self.keyset, self.discovery_uri, self.jwks_uri]
        given = [source for source in sources if source is not None]
        if len(given) != 1:
            raise InvalidConfigurationError(
                "An OIDC token handler needs exactly one key source: "
                "keyset, discovery_uri or jwks_uri.",
            )


@dataclass(frozen=True, slots=True)
class Oauth2TokenHandlerConfig:
    """A handler that introspects a token with its authorization server (RFC 7662).

    The introspection endpoint is reached through a scoped client — the
    application's own HTTP client carrying the endpoint's base URI and this
    resource server's credentials — or through the ``client`` service the
    application registered instead. A ``cache`` service keeps the
    introspection responses of active tokens for ``cache_ttl`` seconds; a
    signed response (RFC 9701) is verified against ``signed_response_keyset``
    or against the keys the issuer's metadata publishes, read through the
    ``signed_response_discovery_cache`` service.

    Attributes:
        introspection_base_uri: The URI the RFC 7662 introspection endpoint
            answers at, unless ``client`` names a service.
        credentials: The basic credentials the introspection endpoint asks
            this resource server for — ``"client:secret"`` or the two as a
            tuple — or ``None`` when the endpoint asks for none.
        client: The type of a registered
            :class:`~xtr_http_client_contracts.HttpClientInterface` service
            that reaches the introspection endpoint, or ``None`` to scope the
            application's own client.
        audiences: The identifiers of this resource server, one of which the
            ``aud`` of the response must name; empty skips the check.
        issuer: The authorization server's identifier, checked against the
            ``iss`` of the response, or ``None`` to skip the check.
        claim: The claim holding the user identifier, or ``None`` to read
            ``sub`` and fall back to ``username``.
        allowed_time_drift: The tolerance, in seconds, on the time claims.
        cache: The type of a registered
            :class:`~xtr_cache_contracts.CacheInterface` service that keeps
            the introspection responses of active tokens, or ``None`` to
            introspect on every request.
        cache_key_prefix: The prefix of the keys the cached responses land
            under.
        cache_ttl: How long a cached response is reused, at most.
        signed_response_algorithms: The signature algorithms a signed
            introspection response (RFC 9701) may use, or ``None`` to accept
            plain introspection responses only.
        signed_response_keyset: A JWKS document pinning the verifying keys,
            or ``None`` to read them from the issuer's metadata.
        signed_response_enforce: Whether a response without a signature is
            refused.
        signed_response_discovery_cache: The type of a registered
            :class:`~xtr_cache_contracts.CacheInterface` service the metadata
            keys are read through, or ``None`` when none is pinned.
        signed_response_discovery_cache_key: The key the metadata document
            lands under.
        type: The discriminator, always ``"oauth2"``.

    Raises:
        InvalidConfigurationError: When neither ``introspection_base_uri`` nor
            ``client`` is given, when ``credentials`` name a service client
            that carries its own, or when the discovery cache is configured
            without the ``issuer`` its metadata URL is built from.
    """

    introspection_base_uri: str | None = None
    credentials: str | tuple[str, str] | None = None
    client: builtins.type | None = None
    audiences: Sequence[str] = field(default_factory=_no_audiences)
    issuer: str | None = None
    claim: str | None = None
    allowed_time_drift: int = 0
    cache: builtins.type | None = None
    cache_key_prefix: str = "oauth2_introspection"
    cache_ttl: int = 60
    signed_response_algorithms: Sequence[str] | None = None
    signed_response_keyset: str | None = None
    signed_response_enforce: bool = True
    signed_response_discovery_cache: builtins.type | None = None
    signed_response_discovery_cache_key: str | None = None
    type: Literal["oauth2"] = "oauth2"

    def __post_init__(self) -> None:
        """Check the endpoint source, and the discovery's issuer."""
        if self.introspection_base_uri is None and self.client is None:
            raise InvalidConfigurationError(
                "An OAuth2 token handler needs the introspection endpoint: set "
                "introspection_base_uri, or name a client service.",
            )
        if self.client is not None and self.credentials is not None:
            raise InvalidConfigurationError(
                "An OAuth2 token handler names a client service, which carries its "
                "own credentials; set credentials only with introspection_base_uri.",
            )
        if self.signed_response_discovery_cache is not None and self.issuer is None:
            raise InvalidConfigurationError(
                "An OAuth2 token handler reading its verifying keys from the "
                "issuer's metadata needs the issuer they are read for; set issuer.",
            )


@dataclass(frozen=True, slots=True)
class OidcUserInfoTokenHandlerConfig:
    """A handler that reads the userinfo endpoint with the token (OIDC Core 5.3).

    The endpoint is reached through a scoped client — the application's own
    HTTP client carrying the endpoint's base URI — or, with a discovery cache
    configured, read off the issuer's discovery document and re-scoped per
    request.

    Attributes:
        userinfo_base_uri: The URI the userinfo endpoint answers at.
        claim: The claim holding the user identifier.
        discovery_cache: The type of a registered
            :class:`~xtr_cache_contracts.CacheInterface` service the issuer's
            discovery document is read through, or ``None`` to keep the
            configured endpoint.
        discovery_cache_key: The key the discovery document lands under.
        type: The discriminator, always ``"oidc_user_info"``.

    Raises:
        InvalidConfigurationError: When no endpoint is given, or a discovery
            cache is configured without its key.
    """

    userinfo_base_uri: str = ""
    claim: str = "sub"
    discovery_cache: builtins.type | None = None
    discovery_cache_key: str | None = None
    type: Literal["oidc_user_info"] = "oidc_user_info"

    def __post_init__(self) -> None:
        """Check the endpoint and the discovery key."""
        if not self.userinfo_base_uri:
            raise InvalidConfigurationError(
                "A userinfo token handler needs the endpoint; set userinfo_base_uri.",
            )
        if self.discovery_cache is not None and self.discovery_cache_key is None:
            raise InvalidConfigurationError(
                "A userinfo token handler reading its endpoint from discovery needs "
                "the key the document lands under; set discovery_cache_key.",
            )


TokenHandlerConfig = (
    ServiceTokenHandlerConfig
    | OidcTokenHandlerConfig
    | Oauth2TokenHandlerConfig
    | OidcUserInfoTokenHandlerConfig
)
"""Every kind of token-handler configuration, told apart by its ``type`` field."""
