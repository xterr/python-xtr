"""A request, a command and a received message each open one unit of work its participants see."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from fastapi import FastAPI
from starlette.requests import HTTPConnection
from xtr_console import Application
from xtr_console.bundle import ConsoleBundle
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.integration.fastapi import attach, request_scope
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_messenger import Envelope, MessageBusInterface, ReceivedStamp
from xtr_messenger.bundle import MessengerBundle

from tests.fixtures import unit_participants_app
from tests.fixtures.unit_participants_app import JOURNAL, Ping

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_dependency_injection.bundle.bundle import AnyBundle

pytestmark = pytest.mark.anyio

_BUNDLES: Mapping[type[AnyBundle], Mapping[str, bool]] = {
    HttpKernelBundle: {"all": True},
    ConsoleBundle: {"all": True},
    MessengerBundle: {"all": True},
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _kernel() -> Kernel:
    return Kernel(unit_participants_app.__name__, env="test", bundles=_BUNDLES)


async def test_a_request_a_command_and_a_received_message_each_begin_and_end_one_unit() -> None:
    app = FastAPI()

    @app.get("/")
    async def home() -> dict[str, str]:
        JOURNAL.append("request")
        return {}

    setup(app, _kernel())
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            JOURNAL.clear()
            _ = await client.get("/")
            request = list(JOURNAL)

    async with await _kernel().boot() as booted:
        JOURNAL.clear()
        code = await (await booted.container.get(Application)).run_async(["fixture:noop"])
        command = list(JOURNAL)

        JOURNAL.clear()
        bus = await booted.container.get(MessageBusInterface)
        _ = await bus.dispatch(Envelope(Ping()), ReceivedStamp("sync"))
        message = list(JOURNAL)

    assert request == ["began", "request", "ended"]
    assert (code, command) == (0, ["began", "command", "ended"])
    assert message == ["began", "handled", "ended"]


async def test_attach_without_a_lifespan_still_runs_participants() -> None:
    app = FastAPI()
    attach(app, _kernel().build())
    connection = HTTPConnection({"type": "http", "app": app})
    JOURNAL.clear()

    async with request_scope(app, connection.scope):
        JOURNAL.append("served")

    assert JOURNAL == ["began", "served", "ended"]
