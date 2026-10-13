"""The endpoints of this server: thin adapters handing each request to its controller."""

from __future__ import annotations

# Every imported name below annotates an endpoint parameter or its return, and
# both the web framework and the container read those annotations when the
# application starts, so none of them can hide under TYPE_CHECKING.
from xtr_dependency_injection import (
    Injected,  # noqa: TC002 -- the container reads these endpoint annotations at runtime
)
from xtr_http_kernel.bridge import (
    Response,  # noqa: TC002 -- the container reads these endpoint annotations at runtime
)
from xtr_http_message_contracts import (  # noqa: TC002 -- the container reads these endpoint annotations at runtime
    ServerRequestInterface,
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

__all__ = ["authorize", "device_code", "introspect", "jwks", "metadata", "revoke", "token"]

# Each endpoint asks the container for the controller answering it, for the
# request being served as an HTTP message, and for the response to answer with,
# and hands all three on. Six of the controllers are built once, from the
# deployment's configuration, and reach whatever is per-request through a
# scoped service. The authorization endpoint's controller is itself
# per-request: it reads the resource owner off the request through the
# firewall's own scoped service, which nothing built once could hold. An
# endpoint a deployment turned off answers 404, as a server that never had it
# would.


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
