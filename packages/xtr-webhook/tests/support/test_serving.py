"""The serving helper honours its own contract: lifespan entered, state bridged."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import FastAPI, Request

from tests.support.serving import serving

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

pytestmark = pytest.mark.anyio


async def test_it_serves_the_application_inside_its_lifespan_with_its_state() -> None:
    opened: list[str] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[dict[str, object]]:
        del app
        opened.append("opened")
        yield {"greeting": "hello"}
        opened.append("closed")

    app = FastAPI(lifespan=lifespan)

    @app.get("/state")
    async def state(request: Request) -> dict[str, str]:
        return {"greeting": cast("str", request.state.greeting)}

    async with serving(app) as client:
        response = await client.get("/state")

    assert response.status_code == 200
    assert response.json() == {"greeting": "hello"}
    assert opened == ["opened", "closed"]
