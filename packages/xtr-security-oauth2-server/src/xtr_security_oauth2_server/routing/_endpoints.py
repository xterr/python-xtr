"""The endpoints of this server, and the resources registering them.

Each endpoint is a module-level function, and each stays the one object: the
discovery document finds the route serving a field by the endpoint it calls —
an identity no move or rename of the route changes — so the table, the
document and the mount all read the very functions below.

Each endpoint asks the container for the controller answering it, for the
request being served as an HTTP message, and for the response to answer with,
and hands all three on. Six of the controllers are built once, from the
deployment's configuration, and reach whatever is per-request through a
scoped service. The authorization endpoint's controller is itself
per-request: it reads the resource owner off the request through the
firewall's own scoped service, which nothing built once could hold. An
endpoint a deployment turned off answers 404, as a server that never had it
would.
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

from xtr_security_oauth2_server._endpoint_paths import (
    AUTHORIZE_PATH,
    DEVICE_CODE_PATH,
    INTROSPECT_PATH,
    JWKS_PATH,
    METADATA_PATH,
    REVOKE_PATH,
    ROUTE_NAMES,
    TOKEN_PATH,
)
from xtr_security_oauth2_server.controller.authorization_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    AuthorizationController,
)
from xtr_security_oauth2_server.controller.device_code_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    DeviceCodeController,
)
from xtr_security_oauth2_server.controller.introspection_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    IntrospectionController,
)
from xtr_security_oauth2_server.controller.jwks_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    JwksController,
)
from xtr_security_oauth2_server.controller.metadata_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    MetadataController,
)
from xtr_security_oauth2_server.controller.revocation_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    RevocationController,
)
from xtr_security_oauth2_server.controller.token_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    TokenController,
)

if TYPE_CHECKING:
    from fastapi import APIRouter

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


async def authorize(
    controller: Injected[AuthorizationController],
    request: Injected[ServerRequestInterface],
    response: Injected[Response],
) -> Response:
    """Read an authorization request, and answer the resource owner's browser.

    Answers ``POST`` as well as ``GET`` because consent is stateless: the form a
    deployment shows posts the original query back here, and this second pass
    is the one a listener approves.
    """
    return await controller.index_action(request, response)


async def token(
    controller: Injected[TokenController],
    request: Injected[ServerRequestInterface],
    response: Injected[Response],
) -> Response:
    """Exchange what a client holds for a token."""
    return await controller.index_action(request, response)


async def device_code(
    controller: Injected[DeviceCodeController],
    request: Injected[ServerRequestInterface],
    response: Injected[Response],
) -> Response:
    """Issue the pair of codes a device with no browser needs."""
    return await controller.index_action(request, response)


async def revoke(
    controller: Injected[RevocationController],
    request: Injected[ServerRequestInterface],
    response: Injected[Response],
) -> Response:
    """Withdraw a token a client is done with."""
    return await controller.index_action(request, response)


async def introspect(
    controller: Injected[IntrospectionController],
    request: Injected[ServerRequestInterface],
    response: Injected[Response],
) -> Response:
    """Say whether a token is live, and what it carries."""
    return await controller.index_action(request, response)


async def metadata(
    controller: Injected[MetadataController],
    request: Injected[ServerRequestInterface],
    response: Injected[Response],
) -> Response:
    """Describe this server, its endpoints and what it accepts."""
    return await controller.index_action(request, response)


async def jwks(
    controller: Injected[JwksController],
    request: Injected[ServerRequestInterface],
    response: Injected[Response],
) -> Response:
    """Publish the keys this server's access tokens are verified against."""
    return await controller.index_action(request, response)


@as_route_resource("oauth2_server")
def oauth2_server_routes(router: APIRouter) -> None:
    """Fill the router with the five protocol endpoints, each under its published name."""
    router.add_api_route(
        AUTHORIZE_PATH,
        authorize,
        methods=["GET", "POST"],
        name=ROUTE_NAMES[AUTHORIZE_PATH],
    )
    router.add_api_route(TOKEN_PATH, token, methods=["POST"], name=ROUTE_NAMES[TOKEN_PATH])
    router.add_api_route(
        DEVICE_CODE_PATH,
        device_code,
        methods=["POST"],
        name=ROUTE_NAMES[DEVICE_CODE_PATH],
    )
    router.add_api_route(REVOKE_PATH, revoke, methods=["POST"], name=ROUTE_NAMES[REVOKE_PATH])
    router.add_api_route(
        INTROSPECT_PATH,
        introspect,
        methods=["POST"],
        name=ROUTE_NAMES[INTROSPECT_PATH],
    )


@as_route_resource("oauth2_server_well_known")
def well_known_routes(router: APIRouter) -> None:
    """Fill the router with the description and the key set, where RFC 8414 fixes them."""
    router.add_api_route(
        METADATA_PATH,
        metadata,
        methods=["GET"],
        name=ROUTE_NAMES[METADATA_PATH],
    )
    router.add_api_route(JWKS_PATH, jwks, methods=["GET"], name=ROUTE_NAMES[JWKS_PATH])
