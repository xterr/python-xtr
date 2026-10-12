"""The router an application mounts to receive webhooks."""

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

from ._endpoint_paths import ROUTE_NAME, WEBHOOK_PATH
from .controller.webhook_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    WebhookController,
)

__all__ = ["routes"]


def routes(prefix: str = "") -> APIRouter:
    """Return the router carrying the endpoint webhooks arrive at.

    An application includes it where it wants the endpoint to be::

        app.include_router(routes())

    ``prefix`` moves it, so an application that keeps everything a stranger
    may call under one path can have it there — ``routes("/hooks")`` serves
    ``/hooks/webhook/{type}``. Wherever it lands, the URL each subscriber is
    given has to be the path actually served, so build it from the route's
    name rather than writing it out again.

    One endpoint serves every subscriber. The type in the URL is what tells
    them apart: it picks the parser that reads the webhook and the secret it
    is checked against, both of which are configuration, so a new subscriber
    needs no new route and no deploy of this module.

    The endpoint is a thin adapter: it asks the container for the controller
    answering it, for the webhook being served as an HTTP message, and for the
    response to answer with, and hands all three on.
    """
    router = APIRouter()

    @router.post(prefix + WEBHOOK_PATH, name=ROUTE_NAME)
    async def webhook(
        type: str,
        controller: Injected[WebhookController],
        request: Injected[ServerRequestInterface],
        response: Injected[Response],
    ) -> Response:
        """Read the webhook that arrived, and answer its sender."""
        return await controller.index_action(type, request, response)

    return router
