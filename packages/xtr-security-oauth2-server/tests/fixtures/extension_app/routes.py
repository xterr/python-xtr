"""The route the add-on serves, read by the tokens this server issues."""

from __future__ import annotations

from typing import Final

# Both the web framework and the container read these endpoint annotations when
# the application starts, so neither can hide under TYPE_CHECKING.
from fastapi import APIRouter
from xtr_dependency_injection import Injected
from xtr_security import Security

__all__ = ["USERINFO_PATH", "extension_routes"]

#: Where the add-on's own endpoint lives.
USERINFO_PATH: Final[str] = "/userinfo"


def extension_routes() -> APIRouter:
    """Return the router the add-on's own endpoint lives on.

    Here the application includes the add-on's router itself; an add-on could
    as well contribute it through a route resource, as this package does. Which
    firewall stands in front of it is the application's to decide: here it is
    the application's own firewall, which reads exactly the access tokens this
    server issues, so the endpoint challenges a request carrying none.
    """
    router = APIRouter()

    @router.get(USERINFO_PATH, name="extension_userinfo")
    async def userinfo(security: Injected[Security]) -> dict[str, str]:
        """Say who the token presented was issued for."""
        token = security.get_token()

        return {"owner": "" if token is None else token.get_user_identifier()}

    return router
