"""Where each endpoint of this server lives, and what its route is called.

Two things read these: the router, which mounts each path, and the bundle,
which builds the discovery document's absolute URLs out of the issuer and the
same paths. They live here so the two cannot drift — a document naming a path
nothing serves is worse than no document at all.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "AUTHORIZE_PATH",
    "DEVICE_CODE_PATH",
    "INTROSPECT_PATH",
    "JWKS_PATH",
    "METADATA_FIELDS",
    "METADATA_PATH",
    "REVOKE_PATH",
    "ROUTE_NAMES",
    "TOKEN_PATH",
]

#: Where a resource owner's browser arrives.
AUTHORIZE_PATH: Final = "/authorize"

#: Where a client exchanges what it holds for a token.
TOKEN_PATH: Final = "/token"  # noqa: S105 -- a URL path, not a secret

#: Where a device with no browser asks for its pair of codes.
DEVICE_CODE_PATH: Final = "/device-code"

#: Where a client asks for a token it holds to be withdrawn.
REVOKE_PATH: Final = "/revoke"

#: Where something asks what this server says about a token.
INTROSPECT_PATH: Final = "/introspect"

#: Where this server describes itself. Fixed by RFC 8414 relative to the
#: issuer, which is why the issuer must be an origin carrying no path of its
#: own.
METADATA_PATH: Final = "/.well-known/oauth-authorization-server"

#: Where the keys this server's access tokens are verified against are read.
JWKS_PATH: Final = "/.well-known/jwks.json"

#: What each route is called, so an application can build a URL to one.
#: Read-only: two modules read it and neither owns it, so neither may change
#: what the other sees.
ROUTE_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        AUTHORIZE_PATH: "oauth2_authorize",
        TOKEN_PATH: "oauth2_token",
        DEVICE_CODE_PATH: "oauth2_device_code",
        REVOKE_PATH: "oauth2_revoke",
        INTROSPECT_PATH: "oauth2_introspect",
        METADATA_PATH: "oauth2_metadata",
        JWKS_PATH: "oauth2_jwks",
    },
)

#: Which field of the discovery document names each path. The metadata endpoint
#: itself is absent: a client has already found it to be reading the document.
METADATA_FIELDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "authorization_endpoint": AUTHORIZE_PATH,
        "token_endpoint": TOKEN_PATH,
        "jwks_uri": JWKS_PATH,
        "revocation_endpoint": REVOKE_PATH,
        "introspection_endpoint": INTROSPECT_PATH,
        "device_authorization_endpoint": DEVICE_CODE_PATH,
    },
)
