"""This server's routes, contributed to the application's routes files.

- :func:`oauth2_server_routes` — resource ``"oauth2_server"``: authorize, token,
  device-code, revoke and introspect, movable under a prefix.
- :func:`well_known_routes` — resource ``"oauth2_server_well_known"``: the RFC 8414
  description and the key set, at the place the standard fixes.

The endpoints live in :mod:`._endpoints`; the discovery document finds each
route by the endpoint it calls, so it publishes them wherever a routes file
puts them.
"""

from __future__ import annotations

from ._endpoints import (
    authorize,
    device_code,
    introspect,
    jwks,
    metadata,
    oauth2_server_routes,
    revoke,
    token,
    well_known_routes,
)

__all__ = [
    "authorize",
    "device_code",
    "introspect",
    "jwks",
    "metadata",
    "oauth2_server_routes",
    "revoke",
    "token",
    "well_known_routes",
]
