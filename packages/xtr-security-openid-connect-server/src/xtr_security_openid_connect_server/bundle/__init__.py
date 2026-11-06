"""The bundle wiring the OpenID Connect provider into an application.

An application lists :class:`OpenIdConnectServerBundle`, which brings the
OAuth 2.0 authorization server's bundle along, and configures it with an
:class:`OpenIdConnectServerConfig`.
"""

from __future__ import annotations

from .openid_connect_server_bundle import OpenIdConnectServerBundle
from .openid_connect_server_config import OpenIdConnectServerConfig

__all__ = ["OpenIdConnectServerBundle", "OpenIdConnectServerConfig"]
