"""The stored device codes, reached by either of the two codes a flow has."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest
from xtr_clock import MockClock

from tests.support.models import EARLIER, LATER, NOW, client_model, device_code_model
from tests.support.orm import CONNECTION, registered, stored
from xtr_security_oauth2_server.manager.device_code_manager_interface import (
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.orm.device_code_manager import DeviceCodeManager
from xtr_security_oauth2_server.model.client import Client

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.orm import Database

pytestmark = pytest.mark.anyio

_POLLS = 5
"""How many requests race to record one poll, or to spend one code."""


def test_it_declares_the_device_code_manager_contract() -> None:
    assert DeviceCodeManagerInterface in DeviceCodeManager.__mro__


async def _manager(database: Database) -> tuple[DeviceCodeManager, Client]:
    """Return a manager and the stored client a device code may be issued to."""
    client = await registered(database.session())

    return await _on(database), client


async def _on(database: Database) -> DeviceCodeManager:
    """Return a manager reading and writing ``database``.

    The manager holds no session of its own: every read and every write opens
    a unit of work of its own, through the scope factory this hands it. A
    second one built here is what the other half of a flow is served by.
    """
    return DeviceCodeManager(await database.scope_factory(), CONNECTION, MockClock(NOW))


async def test_saving_a_code_leaves_the_requests_pending_work_alone(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        unit = database.session()
        client = await registered(unit)
        unit.add(client_model("pending"))

        await (await _on(database)).save(device_code_model(client=client))
        await unit.rollback()

        assert await database.count("oauth2_device_code") == 1
        assert await database.count("oauth2_client") == 1


async def test_only_the_first_caller_to_spend_a_code_is_told_it_did(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(device_code_model(client=client))

        assert await manager.revoke("dc-1") is True
        assert await (await _on(database)).revoke("dc-1") is False
        found = await manager.find("dc-1")
        assert found is not None
        assert found.is_revoked() is True


async def test_many_polls_spending_one_code_leave_exactly_one_winner(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(device_code_model(client=client))
        verdicts: list[bool] = []

        async def spend() -> None:
            verdicts.append(await (await _on(database)).revoke("dc-1"))

        async with anyio.create_task_group() as group:
            for _ in range(_POLLS):
                _ = group.start_soon(spend)

        assert sorted(verdicts) == [*[False] * (_POLLS - 1), True]


async def test_only_the_first_decision_on_a_code_is_recorded(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(device_code_model(client=client))

        assert await manager.record_decision("dc-1", "user-1", user_approved=True) is True
        assert await manager.record_decision("dc-1", "user-2", user_approved=True) is False
        found = await manager.find("dc-1")
        assert found is not None
        assert found.get_user_identifier() == "user-1"
        assert found.get_user_approved() is True


async def test_an_expired_device_code_cannot_be_approved(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(device_code_model(expiry=EARLIER, client=client))

        assert await manager.record_decision("dc-1", "user-1", user_approved=True) is False


async def test_a_spent_device_code_cannot_be_approved(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(device_code_model(client=client))
        _ = await manager.revoke("dc-1")

        assert await manager.record_decision("dc-1", "user-1", user_approved=True) is False


async def test_a_poll_is_recorded_only_against_the_poll_it_read(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(device_code_model(client=client))

        assert await manager.record_poll("dc-1", None, NOW) is True
        assert await manager.record_poll("dc-1", None, LATER) is False
        read = await manager.find("dc-1")
        assert read is not None
        assert await manager.record_poll("dc-1", read.get_last_polled_at(), LATER) is True


async def test_many_polls_read_at_once_record_exactly_one(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(device_code_model(client=client))
        verdicts: list[bool] = []

        async def poll() -> None:
            verdicts.append(await (await _on(database)).record_poll("dc-1", None, NOW))

        async with anyio.create_task_group() as group:
            for _ in range(_POLLS):
                _ = group.start_soon(poll)

        assert sorted(verdicts) == [*[False] * (_POLLS - 1), True]


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
        found = await (await _on(database)).find("dc-1")

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
