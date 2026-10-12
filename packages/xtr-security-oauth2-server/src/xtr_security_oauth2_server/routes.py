"""The router an application mounts to serve this authorization server."""

from __future__ import annotations

# Every imported name below annotates an endpoint parameter or its return, and
# both the web framework and the container read those annotations when the
# application starts, so none of them can hide under TYPE_CHECKING.
from fastapi import APIRouter
from xtr_dependency_injection import (
    Injected,  # noqa: TC002 -- the container reads these endpoint annotations at runtime
)
from xtr_http_kernel.bridge import (
    Response,  # noqa: TC002 -- the container reads these endpoint annotations at runtime
)
from xtr_http_message_contracts import (  # noqa: TC002 -- the container reads these endpoint annotations at runtime
    ServerRequestInterface,
)

from ._endpoint_paths import (
    AUTHORIZE_PATH,
    DEVICE_CODE_PATH,
    INTROSPECT_PATH,
    JWKS_PATH,
    METADATA_PATH,
    REVOKE_PATH,
    ROUTE_NAMES,
    TOKEN_PATH,
)
from .controller.authorization_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    AuthorizationController,
)
from .controller.device_code_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    DeviceCodeController,
)
from .controller.introspection_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    IntrospectionController,
)
from .controller.jwks_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    JwksController,
)
from .controller.metadata_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    MetadataController,
)
from .controller.revocation_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    RevocationController,
)
from .controller.token_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    TokenController,
)

__all__ = ["routes"]


def routes() -> APIRouter:
    """Return the router carrying every endpoint of this server.

    An application includes it where it wants the endpoints to be::

        app.include_router(routes())

    At the root, and not under a prefix: RFC 8414 fixes where this server's
    description lives relative to the issuer, so a prefix would put it
    somewhere no client looks and make the published endpoint URLs wrong.

    Every path is declared, always. The router is built when this module is
    imported, which is before any configuration has been read, so it cannot
    know which endpoints a deployment turned on — an endpoint that is off says
    so by answering ``404``, which is also what a client sees from a server
    that never had it.

    Each endpoint is a thin adapter: it asks the container for the controller
    answering it, for the request being served as an HTTP message, and for the
    response to answer with, and hands all three on. Six of the controllers
    are built once, from the deployment's configuration, and reach whatever is
    per-request through a scoped service — a database session, say. The
    authorization endpoint's controller is itself per-request: it reads the
    resource owner off the request through the firewall's own scoped service,
    which nothing built once could hold.
    """
    router = APIRouter()

    @router.api_route(
        AUTHORIZE_PATH,
        methods=["GET", "POST"],
        name=ROUTE_NAMES[AUTHORIZE_PATH],
    )
    async def authorize(
        controller: Injected[AuthorizationController],
        request: Injected[ServerRequestInterface],
        response: Injected[Response],
    ) -> Response:
        """Read an authorization request, and answer the resource owner's browser.

        Answers ``POST`` as well as ``GET`` because consent is stateless: the
        form a deployment shows posts the original query back here, and this
        second pass is the one a listener approves.
        """
        return await controller.index_action(request, response)

    @router.post(TOKEN_PATH, name=ROUTE_NAMES[TOKEN_PATH])
    async def token(
        controller: Injected[TokenController],
        request: Injected[ServerRequestInterface],
        response: Injected[Response],
    ) -> Response:
        """Exchange what a client holds for a token."""
        return await controller.index_action(request, response)

    @router.post(DEVICE_CODE_PATH, name=ROUTE_NAMES[DEVICE_CODE_PATH])
    async def device_code(
        controller: Injected[DeviceCodeController],
        request: Injected[ServerRequestInterface],
        response: Injected[Response],
    ) -> Response:
        """Issue the pair of codes a device with no browser needs."""
        return await controller.index_action(request, response)

    @router.post(REVOKE_PATH, name=ROUTE_NAMES[REVOKE_PATH])
    async def revoke(
        controller: Injected[RevocationController],
        request: Injected[ServerRequestInterface],
        response: Injected[Response],
    ) -> Response:
        """Withdraw a token a client is done with."""
        return await controller.index_action(request, response)

    @router.post(INTROSPECT_PATH, name=ROUTE_NAMES[INTROSPECT_PATH])
    async def introspect(
        controller: Injected[IntrospectionController],
        request: Injected[ServerRequestInterface],
        response: Injected[Response],
    ) -> Response:
        """Say whether a token is live, and what it carries."""
        return await controller.index_action(request, response)

    @router.get(METADATA_PATH, name=ROUTE_NAMES[METADATA_PATH])
    async def metadata(
        controller: Injected[MetadataController],
        request: Injected[ServerRequestInterface],
        response: Injected[Response],
    ) -> Response:
        """Describe this server, its endpoints and what it accepts."""
        return await controller.index_action(request, response)

    @router.get(JWKS_PATH, name=ROUTE_NAMES[JWKS_PATH])
    async def jwks(
        controller: Injected[JwksController],
        request: Injected[ServerRequestInterface],
        response: Injected[Response],
    ) -> Response:
        """Publish the keys this server's access tokens are verified against."""
        return await controller.index_action(request, response)

    return router
