"""End-to-end: a messenger worker resets the default client after every message it handles."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_http_client_contracts import HttpClientInterface
from xtr_messenger import MessageBusInterface, WorkerFactory

from tests.fixtures.app_http_client_worker.messages import Ping
from tests.fixtures.app_http_client_worker.services import Pings
from xtr_http_client import HttpxHttpClient

pytestmark = pytest.mark.anyio

APP = "tests.fixtures.app_http_client_worker"


async def test_a_worker_handles_one_message_after_another_with_the_real_default_client() -> None:
    async with await Kernel(APP, env="test").boot() as booted:
        bus = await booted.container.get(MessageBusInterface)
        for number in (1, 2):
            _ = await bus.dispatch(Ping(number))
        await (await booted.container.get(WorkerFactory)).worker(["pings"]).run()
        client = await booted.container.get(HttpClientInterface)
        pings = await booted.container.get(Pings)

    assert isinstance(client, HttpxHttpClient)
    assert pings.numbers == [1, 2]
