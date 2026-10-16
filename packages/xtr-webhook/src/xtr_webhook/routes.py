"""The route webhooks arrive at, contributed to the application's routes.

An application includes the ``"webhook"`` resource in one of its routes files,
and may move it under a prefix there. Wherever it lands, the URL a sender is
given has to be the path served, so build it from the route's name — which
:mod:`xtr_webhook._endpoint_paths` pins — rather than writing the path out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Read at runtime: the framework reads the endpoint's annotations when the
# route is mounted, so none of them can hide under TYPE_CHECKING.
from xtr_dependency_injection import Injected  # noqa: TC002 -- read at runtime, as above
from xtr_http_kernel.bridge import Response  # noqa: TC002 -- read at runtime, as above
from xtr_http_kernel.routing.decorator import as_route_resource
from xtr_http_message_contracts import (  # noqa: TC002 -- read at runtime, as above
    ServerRequestInterface,
)

from xtr_webhook._endpoint_paths import ROUTE_NAME, WEBHOOK_PATH
from xtr_webhook.controller.webhook_controller import (  # noqa: TC001 -- read at runtime, as above
    WebhookController,
)

if TYPE_CHECKING:
    from fastapi import APIRouter

__all__ = ["webhook_routes"]


@as_route_resource("webhook")
def webhook_routes(router: APIRouter) -> None:
    """Fill the router with the one endpoint every incoming webhook arrives at.

    One endpoint serves every subscriber. The type in the URL is what tells
    them apart: it picks the parser that reads the webhook and the secret it
    is checked against, both of which are configuration, so a new subscriber
    needs no new route.
    """

    @router.post(WEBHOOK_PATH, name=ROUTE_NAME)
    async def webhook(
        type: str,
        controller: Injected[WebhookController],
        request: Injected[ServerRequestInterface],
        response: Injected[Response],
    ) -> Response:
        """Read the webhook that arrived, and answer its sender."""
        return await controller.index_action(type, request, response)
