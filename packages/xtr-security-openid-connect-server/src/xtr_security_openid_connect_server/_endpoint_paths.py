"""Where each endpoint of the provider lives by default, and what its route is called.

The route loaders contribute each route at its default path under its name;
a routes file may move it, and whatever publishes its URL finds it by the
endpoint it calls, so it is published where it is served.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["ROUTE_NAMES", "USERINFO_PATH"]

#: Where a client reads the claims of the end-user a token was issued for.
USERINFO_PATH: Final = "/userinfo"

#: What each route is called, so an application can build a URL to one.
#: Read-only: the route loaders read it and do not own it.
ROUTE_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        USERINFO_PATH: "openid_connect_server_userinfo",
    },
)
