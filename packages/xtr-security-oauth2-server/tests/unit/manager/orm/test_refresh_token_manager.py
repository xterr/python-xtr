"""The stored refresh tokens, and the one caller a revocation belongs to."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest
from xtr_clock import MockClock

from tests.support.models import EARLIER, LATER, NOW, access_token_model, refresh_token_model
from tests.support.orm import CONNECTION, connections_of, orm_driver, registered, stored
from xtr_security_oauth2_server.manager.orm.refresh_token_manager import RefreshTokenManager
from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (
    RefreshTokenManagerInterface,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.support.orm import Database
    from xtr_security_oauth2_server.model.access_token import AccessToken

pytestmark = pytest.mark.anyio

_REFRESHES = 5
"""How many callers race for one refresh token in the concurrency test."""


def test_it_declares_the_refresh_token_manager_contract() -> None:
    assert RefreshTokenManagerInterface in RefreshTokenManager.__mro__


def _manager(database: Database) -> RefreshTokenManager:
    """Return a manager on a session of its own, as a second request would have."""
    return _on(database.session())


def _on(session: AsyncSession) -> RefreshTokenManager:
    """Return a manager reading and writing through ``session``.

    The manager holds no session of its own: it asks the registry for the one
    of the unit of work it is being used in, which is what this hands it.
    """
    return RefreshTokenManager(connections_of(session), CONNECTION, MockClock(NOW))


async def _beside_an_access_token(database: Database) -> tuple[RefreshTokenManager, AccessToken]:
    """Return a manager and the stored access token a refresh token may name."""
    session = database.session()
    client = await registered(session)
    token = access_token_model(client=client)
    session.add(token)
    await session.commit()

    return _on(session), token


async def test_it_finds_a_token_it_stored(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, token = await _beside_an_access_token(database)

        await manager.save(refresh_token_model(access_token=token))
        found = await manager.find("rt-1")

        assert found is not None
        assert found.get_expiry() == LATER
        assert found.is_revoked() is False


async def test_it_finds_the_access_token_a_refresh_token_was_issued_beside(
    tmp_path: Path,
) -> None:
    async with stored(tmp_path) as database:
        manager, token = await _beside_an_access_token(database)
        await manager.save(refresh_token_model(access_token=token))

        found = await _manager(database).find("rt-1")

        assert found is not None
        beside = found.get_access_token()
        assert beside is not None
        assert beside.get_identifier() == "at-1"


async def test_it_finds_nothing_under_an_unknown_identifier(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        assert await _manager(database).find("nope") is None


async def test_a_saved_token_is_committed_so_another_session_reads_it(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _beside_an_access_token(database)

        await manager.save(refresh_token_model())

        assert await _manager(database).find("rt-1") is not None


async def test_the_first_caller_to_revoke_a_token_is_told_it_did(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _beside_an_access_token(database)
        await manager.save(refresh_token_model())

        assert await manager.revoke("rt-1") is True


async def test_the_second_caller_to_revoke_the_same_token_is_told_it_did_not(
    tmp_path: Path,
) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _beside_an_access_token(database)
        await manager.save(refresh_token_model())
        _ = await manager.revoke("rt-1")

        assert await manager.revoke("rt-1") is False


async def test_the_session_that_revoked_a_token_reads_it_back_revoked(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _beside_an_access_token(database)
        await manager.save(refresh_token_model())

        _ = await manager.revoke("rt-1")
        found = await manager.find("rt-1")

        assert found is not None
        assert found.is_revoked() is True


async def test_a_revocation_is_committed_so_another_session_reads_it_back(
    tmp_path: Path,
) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _beside_an_access_token(database)
        await manager.save(refresh_token_model())

        _ = await manager.revoke("rt-1")
        found = await _manager(database).find("rt-1")

        assert found is not None
        assert found.is_revoked() is True


async def test_revoking_a_token_that_was_never_stored_revoked_nothing(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        assert await _manager(database).revoke("nope") is False


async def test_many_refreshes_of_one_token_leave_exactly_one_winner(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _beside_an_access_token(database)
        await manager.save(refresh_token_model())
        verdicts: list[bool] = []

        async def refresh() -> None:
            verdicts.append(await _manager(database).revoke("rt-1"))

        async with anyio.create_task_group() as group:
            for _ in range(_REFRESHES):
                _ = group.start_soon(refresh)

        assert sorted(verdicts) == [*[False] * (_REFRESHES - 1), True]


async def test_it_sweeps_the_expired_tokens_and_counts_them(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _beside_an_access_token(database)
        await manager.save(refresh_token_model("expired", EARLIER))
        await manager.save(refresh_token_model("alive", LATER))

        assert await manager.clear_expired() == 1
        assert await manager.find("expired") is None
        assert await manager.find("alive") is not None


async def test_sweeping_nothing_reports_nothing(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = await _beside_an_access_token(database)
        await manager.save(refresh_token_model("alive", LATER))

        assert await manager.clear_expired() == 0


async def test_where_no_access_token_is_stored_a_refresh_token_names_none(
    tmp_path: Path,
) -> None:
    async with stored(tmp_path, orm_driver(persist_access_token=False)) as database:
        manager = _manager(database)

        await manager.save(refresh_token_model())
        found = await manager.find("rt-1")

        assert found is not None
        assert found.get_access_token() is None
        assert await manager.revoke("rt-1") is True
