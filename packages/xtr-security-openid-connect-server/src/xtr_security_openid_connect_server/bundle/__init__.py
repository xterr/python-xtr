"""The bundle wiring the OpenID Connect provider into an application.

An application lists :class:`OpenIdConnectServerBundle`, which brings the
OAuth 2.0 authorization server's bundle along, and configures it with an
:class:`OpenIdConnectServerConfig`.

:data:`PROMPT_LISTENER` is the qualifier of the chain step deciding ``prompt``
and ``max_age``: the application lists it in the ``listeners`` of the firewall
that signs end-users in.
"""

from __future__ import annotations

from .openid_connect_server_bundle import PROMPT_LISTENER, OpenIdConnectServerBundle
from .openid_connect_server_config import OpenIdConnectServerConfig

__all__ = ["PROMPT_LISTENER", "OpenIdConnectServerBundle", "OpenIdConnectServerConfig"]
