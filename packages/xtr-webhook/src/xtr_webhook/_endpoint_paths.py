"""Where the endpoint receiving webhooks lives, and what its route is called.

The path and the name are written once, here, rather than at the one place that
mounts them: an application builds a URL to give a sender by the route's name, and
what it hands out has to be the path actually served. A sender that was told a URL
keeps sending to it long after the deploy that changed it.
"""

from __future__ import annotations

from typing import Final

__all__ = ["ROUTE_NAME", "WEBHOOK_PATH"]

#: Where a webhook arrives. The segment is the type the webhook is for — which
#: subscriber sent it, and therefore which parser reads it and which secret it
#: is checked against.
WEBHOOK_PATH: Final = "/webhook/{type}"

#: What the route is called, so an application can build the URL it gives a
#: sender rather than writing the path out again.
ROUTE_NAME: Final = "webhook"
