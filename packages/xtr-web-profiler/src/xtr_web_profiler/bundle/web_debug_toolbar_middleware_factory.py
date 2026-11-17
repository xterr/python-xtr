"""The middleware factory the bundle tags for the kernel to order into the stack."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_web_profiler.web_debug_toolbar_middleware import WebDebugToolbarMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp

    from xtr_web_profiler.csp.content_security_policy_handler import ContentSecurityPolicyHandler
    from xtr_web_profiler.profiler.template_manager import TemplateManager

    from .web_profiler_config import WebProfilerConfig

__all__ = ["WebDebugToolbarMiddlewareFactory"]


@final
class WebDebugToolbarMiddlewareFactory:
    """Wraps a downstream app in the toolbar middleware; tagged for the kernel's stack."""

    __slots__ = ("_config", "_csp", "_manager")

    def __init__(
        self,
        config: WebProfilerConfig,
        manager: TemplateManager,
        csp: ContentSecurityPolicyHandler,
    ) -> None:
        """Hand every middleware built ``config``, ``manager`` and ``csp``."""
        self._config = config
        self._manager = manager
        self._csp = csp

    def __call__(self, app: ASGIApp) -> ASGIApp:
        """Return ``app`` wrapped in the toolbar middleware."""
        return WebDebugToolbarMiddleware(
            app, config=self._config, manager=self._manager, csp=self._csp
        )
