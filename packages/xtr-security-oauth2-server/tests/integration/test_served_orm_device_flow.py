"""A device polling a stored deployment, and what is written down while it waits.

The flow for something that cannot show a browser is the one flow whose state
is written on a request that is answered with an *error*: a poll nobody has
approved yet is refused, and the time of that poll has to survive the refusal
or a device could poll as fast as it liked. Which makes it the proof that the
stored managers commit rather than flush — read here through a session of this
test's own, which is the only place a flush would be invisible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from xtr_security_oauth2_server_core.oauth2_grants import OAuth2Grants

from tests.support.orm_app import orm_kernel, stored_tables, stored_url
from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    SEED_PATH,
    json_of,
    served_application,
    serving,
    text_field,
)
from xtr_security_oauth2_server.model.device_code import DeviceCode

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    import httpx

pytestmark = pytest.mark.anyio


def _application(tmp_path: Path) -> FastAPI:
    """Return the served application of the stored deployment."""
    return served_application(orm_kernel(tmp_path))


async def _device_code(client: httpx.AsyncClient) -> str:
    """Register a client, ask for the pair of codes, and return the one a device polls with."""
    seeded = await client.post(SEED_PATH, params={"grant": ""})
    assert seeded.status_code == 200, seeded.text
    issued = json_of(
        await client.post(
            "/device-code",
            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        ),
    )

    return text_field(issued, "device_code")


async def _poll(client: httpx.AsyncClient, device_code: str) -> httpx.Response:
    """Poll the token endpoint the way a device does."""
    return await client.post(
        "/token",
        data={
            "grant_type": OAuth2Grants.DEVICE_CODE,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "device_code": device_code,
        },
    )


async def _last_polled_at(tmp_path: Path) -> datetime | None:
    """Return the stored poll time, read through a session of this test's own.

    Its own session on its own connection, because that is the only way to
    tell a commit from a flush: a flush inside the request's transaction would
    be invisible here, and would be gone when that transaction was rolled back
    on the way out of the request.
    """
    engine = create_async_engine(stored_url(tmp_path))
    try:
        async with AsyncSession(engine) as session:
            read = await session.execute(select(DeviceCode))

            return read.scalars().one().get_last_polled_at()
    finally:
        await engine.dispose()


async def test_a_poll_nobody_has_approved_yet_still_stores_when_it_polled(
    tmp_path: Path,
) -> None:
    # The answer is an error and the write survives it: the stored managers
    # commit in their write methods, so the rollback on the way out of the
    # request has nothing left to take back.
    async with stored_tables(tmp_path), serving(_application(tmp_path)) as client:
        pending = await _poll(client, await _device_code(client))

        stored = await _last_polled_at(tmp_path)

    assert pending.status_code == 400
    assert text_field(json_of(pending), "error") == "authorization_pending"
    assert stored is not None


async def test_a_poll_told_to_slow_down_stores_its_own_time_as_well(tmp_path: Path) -> None:
    # A device judged against the poll it was last refused for would be told to
    # slow down for ever, so the refused poll is written down too.
    async with stored_tables(tmp_path), serving(_application(tmp_path)) as client:
        device_code = await _device_code(client)
        _ = await _poll(client, device_code)
        first = await _last_polled_at(tmp_path)

        refused = await _poll(client, device_code)
        second = await _last_polled_at(tmp_path)

    assert text_field(json_of(refused), "error") == "slow_down"
    assert first is not None
    assert second is not None
    assert second > first
