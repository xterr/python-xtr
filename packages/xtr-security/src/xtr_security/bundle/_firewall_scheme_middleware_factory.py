"""The middleware factory the http-kernel stack composes over the application."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from ._firewall_scheme_middleware import FirewallSchemeMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp
    from xtr_security_http import FirewallSchemeRegistry

__all__ = ["FirewallSchemeMiddlewareFactory"]


@final
class FirewallSchemeMiddlewareFactory:
    """The middleware factory the http-kernel stack composes over the application.

    Holds the kernel's scheme registry — filled at boot — and wraps the
    downstream application in a
    :class:`FirewallSchemeMiddleware` that activates it per request.
    """

    __slots__ = ("_registry",)

    def __init__(self, registry: FirewallSchemeRegistry) -> None:
        """Record the registry the wrapped middleware activates."""
        self._registry = registry

    def __call__(self, app: ASGIApp) -> ASGIApp:
        """Return ``app`` wrapped so this kernel's schemes are active per request."""
        return FirewallSchemeMiddleware(app, self._registry)
