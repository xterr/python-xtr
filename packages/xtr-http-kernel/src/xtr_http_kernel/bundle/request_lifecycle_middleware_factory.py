"""The middleware factory the bundle tags for the kernel to order into the stack."""

from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003 — read at runtime, as below
from typing import TYPE_CHECKING, final

from starlette.middleware.trustedhost import TrustedHostMiddleware

# Read at runtime: the container fills the constructor from these annotations.
from xtr_event_dispatcher_contracts import EventDispatcherInterface  # noqa: TC002 — read at runtime

from xtr_http_kernel.bridge.http_message_factory_interface import (  # noqa: TC001 — read at runtime, as above
    HttpMessageFactoryInterface,
)
from xtr_http_kernel.request_lifecycle_middleware import RequestLifecycleMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp

__all__ = ["RequestLifecycleMiddlewareFactory"]


@final
class RequestLifecycleMiddlewareFactory:
    """Wraps a downstream app in the lifecycle middleware, around the container's dispatcher.

    Tagged ``http_kernel.middleware`` with the config's
    ``middleware_priority`` as the tag's ``priority``, so the bundle orders
    it into the stack when the kernel is built — highest outermost. The
    message factory it hands the middleware is the container's own, so the
    served request the lifecycle builds its events on is the one the
    application's factories are behind.

    With trusted hosts, a request naming any other host is answered 400 just
    outside the lifecycle, before any of its events.
    """

    __slots__ = ("_dispatcher", "_message_factory", "_trusted_hosts")

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        message_factory: HttpMessageFactoryInterface,
        trusted_hosts: Sequence[str] = (),
    ) -> None:
        """Hand ``dispatcher`` and ``message_factory`` to every middleware built.

        ``trusted_hosts`` as :class:`~xtr_http_kernel.bundle.HttpKernelConfig`
        takes them; empty lets every host through.
        """
        self._dispatcher = dispatcher
        self._message_factory = message_factory
        self._trusted_hosts = tuple(trusted_hosts)

    def __call__(self, app: ASGIApp) -> ASGIApp:
        """Return ``app`` wrapped in the lifecycle middleware, behind the host check if any."""
        lifecycle = RequestLifecycleMiddleware(
            app, dispatcher=self._dispatcher, message_factory=self._message_factory
        )
        if not self._trusted_hosts:
            return lifecycle
        return TrustedHostMiddleware(
            lifecycle, allowed_hosts=self._trusted_hosts, www_redirect=False
        )
