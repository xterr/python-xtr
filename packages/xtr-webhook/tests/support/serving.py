"""Driving a set-up application the way a server does.

The ASGI transport drives the application directly, so nothing runs the
lifespan or copies its state into each connection's scope the way a server
does. :func:`serving` is that server: it enters the application's lifespan,
bridges the yielded state into every request, and hands out a client.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast, final

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from fastapi import FastAPI
    from starlette.types import Receive, Scope, Send

__all__ = ["ServerStateBridge", "serving"]


@final
class ServerStateBridge:
    """What a server adds around an application: lifespan state on each request."""

    def __init__(self, app: FastAPI, state: Mapping[str, object] | None) -> None:
        self._app = app
        self._state = dict(state or {})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["state"] = dict(self._state)
        await self._app(scope, receive, send)


@asynccontextmanager
async def serving(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Serve ``app`` for one application life and yield a client driving it."""
    async with app.router.lifespan_context(app) as state:
        bridge = ServerStateBridge(app, cast("Mapping[str, object] | None", state))
        transport = httpx.ASGITransport(app=bridge, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://served.test") as client:
            yield client
