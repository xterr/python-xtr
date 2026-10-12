"""The stored device codes, reached by either of the two codes a flow has."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_clock import MockClock

from tests.support.models import EARLIER, LATER, NOW, device_code_model
from tests.support.orm import CONNECTION, connections_of, registered, stored
from xtr_security_oauth2_server.manager.device_code_manager_interface import (
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.orm.device_code_manager import DeviceCodeManager
from xtr_security_oauth2_server.model.client import Client

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.support.orm import Database

pytestmark = pytest.mark.anyio


def test_it_declares_the_device_code_manager_contract() -> None:
    assert DeviceCodeManagerInterface in DeviceCodeManager.__mro__


async def _manager(database: Database) -> tuple[DeviceCodeManager, Client]:
    """Return a manager and the stored client a device code may be issued to."""
    session = database.session()
    client = await registered(session)

    return _on(session), client


def _on(session: AsyncSession) -> DeviceCodeManager:
    """Return a manager reading and writing through ``session``.

    The manager holds no session of its own: it asks the registry for the one
    of the unit of work it is being used in, which is what this hands it.
    """
    return DeviceCodeManager(connections_of(session), CONNECTION, MockClock(NOW))


async def test_it_finds_a_code_by_the_identifier_the_device_polls_with(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(device_code_model(client=client))

        found = await manager.find("dc-1")

        assert found is not None
        assert found.get_user_code() == "BCDFGHJK"
        assert found.get_expiry() == LATER
        assert found.get_interval() == 5
        assert found.get_verification_uri() == "https://authorization.example.com/device"
        assert found.get_client().get_identifier() == "client-1"


async def test_it_finds_a_code_by_the_code_its_owner_types_in(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(device_code_model(client=client))

        found = await manager.find_by_user_code("BCDFGHJK")

        assert found is not None
        assert found.get_identifier() == "dc-1"


async def test_it_finds_nothing_under_either_unknown_code(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _manager(database)

        assert await manager.find("nope") is None
        assert await manager.find_by_user_code("ZZZZZZZZ") is None


async def test_what_a_poll_wrote_is_committed_so_the_other_half_reads_it(
    tmp_path: Path,
) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        code = device_code_model(client=client)
        await manager.save(code)

        _ = code.set_user_approved(True)
        _ = code.set_user_identifier("user-1")
        _ = code.set_last_polled_at(NOW)
        await manager.save(code)
        found = await _on(database.session()).find("dc-1")

        assert found is not None
        assert found.get_user_approved() is True
        assert found.get_user_identifier() == "user-1"
        assert found.get_last_polled_at() == NOW


async def test_it_sweeps_the_expired_codes_and_counts_them(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(device_code_model("expired", EARLIER, "AAAAAAAA", client))
        await manager.save(device_code_model("alive", LATER, "BBBBBBBB", client))

        assert await manager.clear_expired() == 1
        assert await manager.find("expired") is None
        assert await manager.find("alive") is not None


async def test_sweeping_nothing_reports_nothing(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _manager(database)

        assert await manager.clear_expired() == 0
