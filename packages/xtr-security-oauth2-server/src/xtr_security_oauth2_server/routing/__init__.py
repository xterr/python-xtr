"""This server's routes, contributed to the application's routes files.

- :func:`oauth2_server_routes` — resource ``"oauth2_server"``: authorize, token,
  device-code, revoke and introspect, movable under a prefix.
- :func:`well_known_routes` — resource ``"oauth2_server_well_known"``: the RFC 8414
  description and the key set, at the place the standard fixes.

The endpoints live in :mod:`._endpoints`; the discovery document finds each
route by the endpoint it calls, so it publishes them wherever a routes file
puts them. :func:`paths_by_endpoint` is that lookup, public so an add-on
serving a route of its own publishes it wherever a routes file puts it too.
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
from .mounted_paths import paths_by_endpoint

__all__ = [
    "authorize",
    "device_code",
    "introspect",
    "jwks",
    "metadata",
    "oauth2_server_routes",
    "paths_by_endpoint",
    "revoke",
    "token",
    "well_known_routes",
]
