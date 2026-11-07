"""The provider's endpoints, and the resource registering them.

Each endpoint is a module-level function, and stays the one object: what
publishes an endpoint's URL finds its route by the function it calls — an
identity no move or rename of the route changes.

Each endpoint asks the container for the controller answering it, for the
request being served as an HTTP message, and for the response to answer with,
and hands all three on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Every imported name below annotates an endpoint parameter or its return, and
# both the web framework and the container read those annotations when the
# application starts, so none of them can hide under TYPE_CHECKING.
from xtr_dependency_injection import (
    Injected,  # noqa: TC002 -- the container reads these endpoint annotations at runtime
)
from xtr_http_kernel.bridge import (
    Response,  # noqa: TC002 -- the container reads these endpoint annotations at runtime
)
from xtr_http_kernel.routing.decorator import as_route_resource
from xtr_http_message_contracts import (  # noqa: TC002 -- the container reads these endpoint annotations at runtime
    ServerRequestInterface,
)

from xtr_security_openid_connect_server._endpoint_paths import ROUTE_NAMES, USERINFO_PATH
from xtr_security_openid_connect_server.controller.user_info_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    UserInfoController,
)

if TYPE_CHECKING:
    from fastapi import APIRouter

__all__ = ["openid_connect_server_routes", "userinfo"]


async def userinfo(
    controller: Injected[UserInfoController],
    request: Injected[ServerRequestInterface],
    response: Injected[Response],
) -> Response:
    """Describe the end-user the presented access token stands for.

    Answers ``POST`` as well as ``GET``, as OpenID Connect Core 5.3.1 asks.
    """
    return await controller.index_action(request, response)


@as_route_resource("openid_connect_server")
def openid_connect_server_routes(router: APIRouter) -> None:
    """Fill the router with the userinfo endpoint, under its published name."""
    router.add_api_route(
        USERINFO_PATH,
        userinfo,
        methods=["GET", "POST"],
        name=ROUTE_NAMES[USERINFO_PATH],
    )
