"""The xtr-dependency-injection bundle for xtr-web-profiler."""

from __future__ import annotations

from .web_debug_toolbar_middleware_factory import WebDebugToolbarMiddlewareFactory
from .web_profiler_bundle import WEB_DEBUG_TOOLBAR_PRIORITY, WebProfilerBundle
from .web_profiler_config import WebProfilerConfig

__all__ = [
    "WEB_DEBUG_TOOLBAR_PRIORITY",
    "WebDebugToolbarMiddlewareFactory",
    "WebProfilerBundle",
    "WebProfilerConfig",
]
