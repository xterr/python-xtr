"""The stored authorization codes, read, written and swept."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_clock import MockClock

from tests.support.models import EARLIER, LATER, NOW, authorization_code_model
from tests.support.orm import CONNECTION, connections_of, registered, selects, stored
from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.orm.authorization_code_manager import (
    AuthorizationCodeManager,
)
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.support.orm import Database

pytestmark = pytest.mark.anyio


def test_it_declares_the_authorization_code_manager_contract() -> None:
    assert AuthorizationCodeManagerInterface in AuthorizationCodeManager.__mro__


async def _manager(database: Database) -> tuple[AuthorizationCodeManager, Client]:
    """Return a manager and the stored client a code may be issued to."""
    session = database.session()
    client = await registered(session)

    return _on(session), client


def _on(session: AsyncSession) -> AuthorizationCodeManager:
    """Return a manager reading and writing through ``session``.

    The manager holds no session of its own: it asks the registry for the one
    of the unit of work it is being used in, which is what this hands it.
    """
    return AuthorizationCodeManager(connections_of(session), CONNECTION, MockClock(NOW))


async def test_it_finds_a_code_it_stored(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(authorization_code_model(client=client, scopes=("read",)))

        found = await manager.find("ac-1")

        assert found is not None
        assert found.get_expiry() == LATER
        assert found.get_user_identifier() == "user-1"
        assert found.get_scopes() == (Scope("read"),)
        assert found.get_client().get_identifier() == "client-1"


async def test_it_reads_a_code_and_its_client_in_one_statement(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(authorization_code_model(client=client))
        database.session().expunge_all()

        with database.watching() as statements:
            _ = await _on(database.session()).find("ac-1")

            assert len(selects(statements)) == 1


async def test_it_finds_nothing_under_an_unknown_identifier(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _manager(database)

        assert await manager.find("nope") is None


async def test_a_redeemed_code_reads_back_revoked(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        code = authorization_code_model(client=client)
        await manager.save(code)

        await manager.save(code.revoke())
        found = await _on(database.session()).find("ac-1")

        assert found is not None
        assert found.is_revoked() is True


async def test_a_saved_code_is_committed_so_another_session_reads_it(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)

        await manager.save(authorization_code_model(client=client))

        assert await database.count("oauth2_authorization_code") == 1


async def test_it_sweeps_the_expired_codes_and_counts_them(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(authorization_code_model("expired", EARLIER, client))
        await manager.save(authorization_code_model("alive", LATER, client))

        assert await manager.clear_expired() == 1
        assert await manager.find("expired") is None
        assert await manager.find("alive") is not None


async def test_a_code_expiring_this_very_instant_is_kept(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, client = await _manager(database)
        await manager.save(authorization_code_model("on-the-boundary", NOW, client))

        assert await manager.clear_expired() == 0


async def test_sweeping_nothing_reports_nothing(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _manager(database)

        assert await manager.clear_expired() == 0
