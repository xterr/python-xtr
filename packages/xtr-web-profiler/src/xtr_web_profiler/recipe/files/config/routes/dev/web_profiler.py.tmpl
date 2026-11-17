"""Where the development environment serves the debug toolbar and the profiler's pages.

This file is what registers them, and it sits in the dev environment's folder,
so nothing of the profiler is routed in any other environment. Deleting it
takes the toolbar and the pages down.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI

__all__ = ["web_profiler"]


@as_routes
def web_profiler(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Serve the toolbar under /_wdt and the profiler's pages under /_profiler."""
    app.include_router(resources["web_profiler_wdt"], prefix="/_wdt")
    app.include_router(resources["web_profiler"], prefix="/_profiler")
