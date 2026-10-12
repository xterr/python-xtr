"""The stored access tokens, read, written and swept against a real database."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from xtr_clock import MockClock

from tests.support.models import EARLIER, LATER, NOW, access_token_model, refresh_token_model
from tests.support.orm import CONNECTION, connections_of, orm_driver, registered, selects, stored
from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.orm.access_token_manager import AccessTokenManager
from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.anyio


def _manager(session: AsyncSession, persist_access_token: bool = True) -> AccessTokenManager:
    """Return a manager that reads and writes through ``session``.

    The manager is a singleton and holds no session: it asks the registry for
    the one of the unit of work it is being used in, which is what a request
    gives it and what this hands it.
    """
    return AccessTokenManager(
        connections_of(session),
        CONNECTION,
        MockClock(NOW),
        persist_access_token,
    )


def test_it_declares_the_access_token_manager_contract() -> None:
    assert AccessTokenManagerInterface in AccessTokenManager.__mro__


async def test_it_finds_a_token_it_stored(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        manager = _manager(session)
        await manager.save(access_token_model(client=client, scopes=("read",)))

        found = await manager.find("at-1")

        assert found is not None
        assert found.get_expiry() == LATER
        assert found.get_user_identifier() == "user-1"
        assert found.get_scopes() == (Scope("read"),)
        assert found.get_client().get_identifier() == "client-1"


async def test_it_reads_a_token_and_its_client_in_one_statement(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        manager = _manager(session)
        await manager.save(access_token_model(client=client))
        session.expunge_all()

        with database.watching() as statements:
            _ = await manager.find("at-1")

            assert len(selects(statements)) == 1


async def test_reading_a_token_back_does_not_run_the_models_constructor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        manager = _manager(session)
        await manager.save(access_token_model(client=client))
        session.expunge_all()
        monkeypatch.setattr(AccessToken, "__init__", _refuse)
        try:
            # Undone before the mapping is, so what the mapping put on the
            # class is what the mapping takes back off it.
            assert await manager.find("at-1") is not None
        finally:
            monkeypatch.undo()


async def test_a_revoked_token_reads_back_revoked(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        manager = _manager(session)
        token = access_token_model(client=client)
        await manager.save(token)

        await manager.save(token.revoke())
        session.expunge_all()
        found = await manager.find("at-1")

        assert found is not None
        assert found.is_revoked() is True


async def test_it_finds_nothing_under_an_unknown_identifier(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager = _manager(database.session())

        assert await manager.find("nope") is None


async def test_a_saved_token_is_committed_so_another_session_reads_it(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        manager = _manager(session)

        await manager.save(access_token_model(client=client))

        assert await database.count("oauth2_access_token") == 1


async def test_it_sweeps_the_expired_tokens_and_counts_them(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        manager = _manager(session)
        await manager.save(access_token_model("expired", EARLIER, client))
        await manager.save(access_token_model("alive", LATER, client))

        assert await manager.clear_expired() == 1
        assert await manager.find("expired") is None
        assert await manager.find("alive") is not None


async def test_a_token_expiring_this_very_instant_is_kept(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        manager = _manager(session)
        await manager.save(access_token_model("on-the-boundary", NOW, client))

        assert await manager.clear_expired() == 0
        assert await manager.find("on-the-boundary") is not None


async def test_sweeping_nothing_reports_nothing(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager = _manager(database.session())

        assert await manager.clear_expired() == 0


async def test_a_refresh_token_loses_the_expired_token_it_was_issued_beside(
    tmp_path: Path,
) -> None:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        manager = _manager(session)
        token = access_token_model("expired", EARLIER, client)
        await manager.save(token)
        session.add(refresh_token_model("rt-1", LATER, token))
        await session.commit()

        assert await manager.clear_expired() == 1
        assert await database.count("oauth2_refresh_token") == 1

        beside = database.table("oauth2_refresh_token").c["access_token"]
        left = await session.execute(select(beside))
        assert left.scalar_one() is None


async def test_it_stores_and_reads_nothing_where_tokens_are_not_persisted(
    tmp_path: Path,
) -> None:
    async with stored(tmp_path, orm_driver(persist_access_token=False)) as database:
        session = database.session()
        client = await registered(session)
        manager = _manager(session, persist_access_token=False)

        await manager.save(access_token_model(client=client))

        assert await manager.find("at-1") is None
        assert await manager.clear_expired() == 0


def _refuse(*_arguments: object, **_named: object) -> None:
    """Stand in for a constructor that must not run on a load."""
    raise AssertionError("the model's constructor ran on a load")
