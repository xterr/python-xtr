"""The provider's routes, contributed to the application's routes files.

- :func:`openid_connect_server_routes` — resource ``"openid_connect_server"``:
  the userinfo endpoint, movable under a prefix.
- :func:`well_known_routes` — resource ``"openid_connect_server_well_known"``:
  the configuration document, at the fixed path under the issuer.

The endpoints live in :mod:`._endpoints`; :func:`userinfo` is public so what
publishes its URL can find the route serving it wherever a routes file puts it.
Nothing here is served until a routes file includes the resource, and the
firewall in front of it is the application's to put there.
"""

from __future__ import annotations

from ._endpoints import (
    openid_configuration,
    openid_connect_server_routes,
    userinfo,
    well_known_routes,
)

__all__ = [
    "openid_configuration",
    "openid_connect_server_routes",
    "userinfo",
    "well_known_routes",
]
