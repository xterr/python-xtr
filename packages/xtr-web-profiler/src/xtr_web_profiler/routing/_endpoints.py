"""The profiler's endpoints, and the two route resources registering them.

``web_profiler_wdt`` holds what every page's toolbar fetches — the fragment
and its stylesheet — and ``web_profiler`` the profiler's own pages. An
application includes both from a routes file of its development environment,
usually under ``/_wdt`` and ``/_profiler``; nothing is served otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Every name below annotates an endpoint parameter or its return, and both the
# web framework and the container read those annotations when the application
# starts, so none of them can hide under TYPE_CHECKING.
from starlette.requests import Request  # noqa: TC002 — read at runtime by the web framework
from xtr_dependency_injection import Injected  # noqa: TC002 — read at runtime by the container
from xtr_http_kernel.bridge import Response  # noqa: TC002 — read at runtime by the container
from xtr_http_kernel.routing.decorator import as_route_resource

from xtr_web_profiler.controller.profiler_controller import (  # noqa: TC001 — read at runtime by the container
    ProfilerController,
)

if TYPE_CHECKING:
    from fastapi import APIRouter

__all__ = [
    "home",
    "open_file",
    "panel",
    "search",
    "search_results",
    "stylesheet",
    "toolbar",
    "web_debug_toolbar_routes",
    "web_profiler_routes",
]


async def toolbar(
    token: str,
    request: Request,
    controller: Injected[ProfilerController],
    response: Injected[Response],
) -> Response:
    """Answer the toolbar fragment of the profile ``token``."""
    return await controller.toolbar(request, response, token)


async def stylesheet(
    controller: Injected[ProfilerController],
    response: Injected[Response],
) -> Response:
    """Answer the toolbar's stylesheet."""
    return await controller.stylesheet(response)


async def home(
    request: Request,
    controller: Injected[ProfilerController],
    response: Injected[Response],
) -> Response:
    """Send the browser to the latest profiles."""
    return await controller.home(request, response)


async def search(
    request: Request,
    controller: Injected[ProfilerController],
    response: Injected[Response],
) -> Response:
    """Send the browser to what the search asks for."""
    return await controller.search(request, response)


async def search_results(
    token: str,
    request: Request,
    controller: Injected[ProfilerController],
    response: Injected[Response],
) -> Response:
    """Answer the profiles the search finds."""
    return await controller.search_results(request, response, token)


async def open_file(
    request: Request,
    controller: Injected[ProfilerController],
    response: Injected[Response],
) -> Response:
    """Answer a source file of the project."""
    return await controller.open_file(request, response)


async def panel(
    token: str,
    request: Request,
    controller: Injected[ProfilerController],
    response: Injected[Response],
) -> Response:
    """Answer the profile ``token``, one panel open."""
    return await controller.panel(request, response, token)


@as_route_resource("web_profiler_wdt")
def web_debug_toolbar_routes(router: APIRouter) -> None:
    """Fill ``router`` with what every page's toolbar fetches."""
    # The stylesheet first: a token route declared before it would answer /styles.
    _ = router.get("/styles", name="_wdt_stylesheet", include_in_schema=False)(stylesheet)
    _ = router.get("/{token}", name="_wdt", include_in_schema=False)(toolbar)


@as_route_resource("web_profiler")
def web_profiler_routes(router: APIRouter) -> None:
    """Fill ``router`` with the profiler's pages."""
    _ = router.get("/", name="_profiler_home", include_in_schema=False)(home)
    _ = router.get("/search", name="_profiler_search", include_in_schema=False)(search)
    _ = router.get("/open", name="_profiler_open_file", include_in_schema=False)(open_file)
    _ = router.get(
        "/{token}/search/results", name="_profiler_search_results", include_in_schema=False
    )(search_results)
    _ = router.get("/{token}", name="_profiler", include_in_schema=False)(panel)
