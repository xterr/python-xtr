"""This server's routes, contributed to the application's route table.

- :class:`OAuth2ServerRouteLoader` — resource ``"oauth2_server"``: authorize, token,
  device-code, revoke and introspect, movable under a prefix.
- :class:`WellKnownRouteLoader` — resource ``"oauth2_server_well_known"``: the RFC 8414
  description and the key set, at the place the standard fixes.
"""

from __future__ import annotations

from .oauth2_server_route_loader import OAuth2ServerRouteLoader
from .well_known_route_loader import WellKnownRouteLoader

__all__ = ["OAuth2ServerRouteLoader", "WellKnownRouteLoader"]
