"""Serving the fixture application the way a server does, and building it."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast, final

import httpx
from fastapi import FastAPI
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup

from xtr_web_profiler.bundle import WebProfilerBundle

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Mapping

    from starlette.types import Receive, Scope, Send

__all__ = ["PAGE", "application", "serving"]

PAGE = "<html><head><title>Shop</title></head><body><h1>Books</h1></body></html>"
"""What the page route answers, before any toolbar."""


def application(*overrides: str, env: str = "dev", compress: bool = False) -> FastAPI:
    """Build the fixture application on a kernel of ``env``, with the given override modules.

    ``compress`` adds the framework's gzip middleware, as an application usually does —
    before ``setup``, so inside the kernel's middleware.
    """
    kernel = Kernel(
        "tests.fixtures.shop",
        env=env,
        debug=True,
        bundles={WebProfilerBundle: {"all": True}},
        resources=(
            "tests.fixtures.shop",
            *(f"tests.fixtures.shop_overrides.{override}" for override in overrides),
        ),
    )
    app = FastAPI()

    @app.get("/page", name="page")
    async def page() -> HTMLResponse:
        return HTMLResponse(PAGE)

    @app.get("/data")
    async def data() -> JSONResponse:
        return JSONResponse({"books": 3})

    @app.get("/away")
    async def away() -> RedirectResponse:
        return RedirectResponse("/page", status_code=302)

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"<html><body><p>streamed</p></bo"
            yield b"dy></html>"

        return StreamingResponse(chunks(), media_type="text/html")

    @app.get("/download")
    async def download() -> HTMLResponse:
        return HTMLResponse(PAGE, headers={"content-disposition": "attachment; filename=a.html"})

    @app.get("/protected")
    async def protected() -> HTMLResponse:
        return HTMLResponse(
            PAGE, headers={"content-security-policy": "default-src 'self'; script-src 'self'"}
        )

    @app.get("/boom")
    async def boom() -> HTMLResponse:
        message = "the shelf collapsed"
        raise RuntimeError(message)

    if compress:
        app.add_middleware(GZipMiddleware, minimum_size=10)
    setup(app, kernel)
    return app


@final
class _StateBridge:
    """What a server adds around an application: the lifespan's state on each request."""

    def __init__(self, app: FastAPI, state: Mapping[str, object] | None) -> None:
        self._app = app
        self._state = dict(state or {})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["state"] = dict(self._state)
        await self._app(scope, receive, send)


@asynccontextmanager
async def serving(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient]:
    """Serve ``app`` for one application life and yield a client driving it."""
    async with app.router.lifespan_context(app) as state:
        bridge = _StateBridge(app, cast("Mapping[str, object] | None", state))
        transport = httpx.ASGITransport(app=bridge, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://shop.test") as client:
            yield client
