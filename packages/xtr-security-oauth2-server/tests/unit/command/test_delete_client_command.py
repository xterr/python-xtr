"""``oauth2-server:delete-client`` withdraws a registration, or says there was none."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import CommandTester, ExitCode

from tests.support.console import console_kernel, running
from tests.support.models import client_model
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio

_COMMAND = "oauth2-server:delete-client"

_IDENTIFIER = "foobar"


@pytest.fixture
async def console() -> AsyncIterator[tuple[CommandTester, ContainerInterface]]:
    """Register one client, then hand over the command and the container."""
    async with running(console_kernel()) as (application, container):
        clients = await container.get(ClientManagerInterface)
        await clients.save(client_model(_IDENTIFIER))
        yield CommandTester(application, _COMMAND, width=200), container


async def test_it_withdraws_the_registration(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await tester.execute([_IDENTIFIER])

    assert code == ExitCode.SUCCESS
    assert "OAuth2 client deleted successfully." in tester.display
    clients = await container.get(ClientManagerInterface)
    assert await clients.find(_IDENTIFIER) is None


async def test_an_unknown_client_is_reported_rather_than_answered_as_withdrawn(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await tester.execute(["nobody"])

    assert code == ExitCode.FAILURE
    assert 'OAuth2 client identified as "nobody" does not exist.' in tester.display
    clients = await container.get(ClientManagerInterface)
    assert await clients.find(_IDENTIFIER) is not None
