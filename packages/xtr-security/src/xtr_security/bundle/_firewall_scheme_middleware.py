"""The middleware that makes a kernel's firewall schemes readable while it serves.

A firewall's OpenAPI model is read synchronously while the generated schema is
built, from a process-level holder the http layer keeps. This middleware makes
the kernel's own scheme registry the active one for the span of every request it
serves, so the schema read inside a ``/openapi.json`` request — synchronous, and
therefore never interleaved with another kernel's — sees this kernel's firewalls
and no other's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_http import active_firewall_schemes

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send
    from xtr_security_http import FirewallSchemeRegistry

__all__ = ["FirewallSchemeMiddleware"]


@final
class FirewallSchemeMiddleware:
    """Activates one kernel's firewall scheme registry for a request's span."""

    __slots__ = ("_app", "_registry")

    def __init__(self, app: ASGIApp, registry: FirewallSchemeRegistry) -> None:
        """Wrap ``app``, activating ``registry`` around each request it serves."""
        self._app = app
        self._registry = registry

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve the request with this kernel's scheme registry active."""
        with active_firewall_schemes(self._registry):
            await self._app(scope, receive, send)
