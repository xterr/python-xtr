"""The route resources of the profiler: ``web_profiler_wdt`` and ``web_profiler``."""

from __future__ import annotations

from ._endpoints import web_debug_toolbar_routes, web_profiler_routes

__all__ = ["web_debug_toolbar_routes", "web_profiler_routes"]
