"""How a bearer access token is validated, described as inert data.

A token handler turns an access-token string into a user badge. Two kinds ship
here — a handler the container provides, and one that verifies a third-party
OIDC issuer's tokens — and the ``type`` field tells the kinds apart so a later
package (an introspection handler) adds its own through the token-handler factory
registry (seam S-2).
"""

from __future__ import annotations

import builtins  # noqa: TC003 -- field type read at runtime
from collections.abc import Sequence  # noqa: TC003 -- field type read at runtime
from dataclasses import dataclass, field
from typing import Literal

from xtr_security.exception import InvalidConfigurationError

__all__ = [
    "OidcTokenHandlerConfig",
    "ServiceTokenHandlerConfig",
    "TokenHandlerConfig",
]


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


def _one_issuer() -> Sequence[str]:
    """The empty issuer list an OIDC handler configuration starts with."""
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
        leeway: The clock skew, in seconds, allowed on the time claims.
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
            not exactly one of ``keyset``, ``discovery_uri`` or ``jwks_uri``.
    """

    issuers: Sequence[str] = field(default_factory=_one_issuer)
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
                key source is not exactly one.
        """
        if not self.issuers:
            raise InvalidConfigurationError(
                "An OIDC token handler needs at least one trusted issuer.",
            )
        if not self.audience:
            raise InvalidConfigurationError("An OIDC token handler needs an audience.")
        sources = [self.keyset, self.discovery_uri, self.jwks_uri]
        given = [source for source in sources if source is not None]
        if len(given) != 1:
            raise InvalidConfigurationError(
                "An OIDC token handler needs exactly one key source: "
                "keyset, discovery_uri or jwks_uri.",
            )


TokenHandlerConfig = ServiceTokenHandlerConfig | OidcTokenHandlerConfig
"""Every kind of token-handler configuration, told apart by its ``type`` field."""
