"""The endpoint webhooks arrive at: a thin adapter handing each one to its controller."""

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

from xtr_webhook.controller.webhook_controller import (  # noqa: TC001 -- the container reads these endpoint annotations at runtime
    WebhookController,
)

__all__ = ["webhook"]


async def webhook(
    type: str,  # noqa: A002 -- the path segment the endpoint is declared with
    controller: Injected[WebhookController],
    request: Injected[ServerRequestInterface],
    response: Injected[Response],
) -> Response:
    """Read the webhook that arrived, and answer its sender.

    One endpoint serves every subscriber. The type in the URL is what tells them
    apart: it picks the parser that reads the webhook and the secret it is
    checked against, both of which are configuration, so a new subscriber needs
    no new route.
    """
    return await controller.index_action(type, request, response)
