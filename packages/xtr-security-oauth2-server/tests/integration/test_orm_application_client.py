"""An application's own client class, with the credentials pointing at it.

An application whose clients need columns of its own maps the class itself, on
whichever base it already uses, and names it in the configuration. What has to
hold then is everything a shipped client gives: the registration round-trips,
a credential reads its client back through the relationship, the package builds
no client table of its own, and a client's removal takes its credentials with
it.

An application's client class is mapped once, when its module is imported, so
its table is in definitions the whole process shares. Every test here therefore
takes a table prefix of its own: its credential tables are then its own too, and
no test is mapped against columns another test was mapped against — which is
what a server has anyway, since it maps one deployment and never a second.
"""

from __future__ import annotations

from itertools import count
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from xtr_clock import MockClock

from tests.support.app_client import AuditAppClient, PlainAppClient
from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.models import LATER, NOW, authorization_code_model, device_code_model
from tests.support.orm import CONNECTION, connections_of, orm_driver, selects, stored
from xtr_security_oauth2_server.manager.orm.authorization_code_manager import (
    AuthorizationCodeManager,
)
from xtr_security_oauth2_server.manager.orm.client_manager import ClientManager
from xtr_security_oauth2_server.manager.orm.device_code_manager import DeviceCodeManager
from xtr_security_oauth2_server.value_object.grant import Grant

if TYPE_CHECKING:
    from pathlib import Path
    from typing import TypeAlias

    from sqlalchemy import MetaData
    from sqlalchemy.ext.asyncio import AsyncSession

    AppClient: TypeAlias = PlainAppClient | AuditAppClient
    AppClientClass: TypeAlias = type[PlainAppClient | AuditAppClient]

pytestmark = pytest.mark.anyio

_BASES: list[AppClientClass] = [PlainAppClient, AuditAppClient]
"""The two bases an application realistically maps its own client on."""

_RUNS = count()
"""What makes each test's prefix its own."""


@pytest.fixture
def prefix() -> str:
    """Return a table prefix no other test in this module uses."""
    return f"oauth2_{next(_RUNS)}_"


def _definitions(client_class: AppClientClass) -> MetaData:
    """Return the definitions the application mapped ``client_class`` into."""
    return client_class.metadata


def _app_client(client_class: AppClientClass, identifier: str = "client-1") -> AppClient:
    """Return an application client registered for one grant, with its own column."""
    client = client_class("App client", identifier, "hashed-secret")
    _ = client.set_grants(Grant("authorization_code"))
    client.tenant = "tenant-1"

    return client


def _clients(session: AsyncSession, client_class: AppClientClass) -> ClientManager:
    """Return a client manager reading and writing through ``session``."""
    return ClientManager(
        connections_of(session),
        CONNECTION,
        RecordingEventDispatcher(),
        client_class,
    )


def _codes(session: AsyncSession) -> AuthorizationCodeManager:
    """Return an authorization-code manager reading and writing through ``session``."""
    return AuthorizationCodeManager(connections_of(session), CONNECTION, MockClock(NOW))


@pytest.mark.parametrize("client_class", _BASES)
async def test_the_package_builds_no_client_table_of_its_own(
    tmp_path: Path, prefix: str, client_class: AppClientClass
) -> None:
    driver = orm_driver(client_class=client_class, table_prefix=prefix)
    async with stored(tmp_path, driver, _definitions(client_class)) as database:
        assert f"{prefix}client" not in database.metadata.tables
        assert f"{prefix}access_token" in database.metadata.tables


@pytest.mark.parametrize("client_class", _BASES)
async def test_a_registration_round_trips_beside_the_applications_own_column(
    tmp_path: Path, prefix: str, client_class: AppClientClass
) -> None:
    driver = orm_driver(client_class=client_class, table_prefix=prefix)
    async with stored(tmp_path, driver, _definitions(client_class)) as database:
        session = database.session()
        manager = _clients(session, client_class)
        await manager.save(_app_client(client_class))
        session.expunge_all()

        found = await manager.find("client-1")

        assert isinstance(found, PlainAppClient | AuditAppClient)
        assert found.get_name() == "App client"
        assert found.get_secret() == "hashed-secret"
        assert found.get_grants() == (Grant("authorization_code"),)
        assert found.is_active() is True
        assert found.tenant == "tenant-1"


@pytest.mark.parametrize("client_class", _BASES)
async def test_a_credential_reads_its_application_client_in_one_statement(
    tmp_path: Path, prefix: str, client_class: AppClientClass
) -> None:
    driver = orm_driver(client_class=client_class, table_prefix=prefix)
    async with stored(tmp_path, driver, _definitions(client_class)) as database:
        session = database.session()
        client = _app_client(client_class)
        session.add(client)
        await session.commit()
        codes = _codes(session)
        await codes.save(authorization_code_model(client=client))
        session.expunge_all()

        with database.watching() as statements:
            found = await codes.find("ac-1")

            assert len(selects(statements)) == 1

        assert found is not None
        assert found.get_client().get_identifier() == "client-1"


@pytest.mark.parametrize("client_class", _BASES)
async def test_removing_an_application_client_takes_its_credentials_with_it(
    tmp_path: Path, prefix: str, client_class: AppClientClass
) -> None:
    driver = orm_driver(client_class=client_class, table_prefix=prefix)
    async with stored(tmp_path, driver, _definitions(client_class)) as database:
        session = database.session()
        manager = _clients(session, client_class)
        await manager.save(_app_client(client_class))
        registered = await manager.find("client-1")
        assert registered is not None
        await _codes(session).save(
            authorization_code_model(client=registered),
        )
        await DeviceCodeManager(connections_of(session), CONNECTION, MockClock(NOW)).save(
            device_code_model(client=registered),
        )

        await manager.remove(registered)

        assert await database.count(f"{prefix}authorization_code") == 0
        assert await database.count(f"{prefix}device_code") == 0


async def test_an_audited_client_keeps_its_own_primary_key(tmp_path: Path, prefix: str) -> None:
    driver = orm_driver(client_class=AuditAppClient, table_prefix=prefix)
    async with stored(tmp_path, driver, AuditAppClient.metadata) as database:
        session = database.session()
        manager = _clients(session, AuditAppClient)
        await manager.save(_app_client(AuditAppClient))
        session.expunge_all()

        read = await session.execute(select(AuditAppClient))
        found = read.scalars().one()

        assert found.id is not None
        assert found.get_identifier() == "client-1"
        assert found.created_at is not None


async def test_a_credential_is_stored_beside_the_client_it_names(
    tmp_path: Path, prefix: str
) -> None:
    driver = orm_driver(client_class=PlainAppClient, table_prefix=prefix)
    async with stored(tmp_path, driver, PlainAppClient.metadata) as database:
        session = database.session()

        await _codes(session).save(
            authorization_code_model("ac-1", LATER, _app_client(PlainAppClient)),
        )

        assert await database.count(f"{prefix}authorization_code") == 1
        assert await database.count("app_client") == 1
