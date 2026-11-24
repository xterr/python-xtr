"""The orm fixtures bundle on its own: zero configuration, and what it registers."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config
from xtr_orm.bundle import OrmBundle

from xtr_orm_fixtures import TableDefinitions
from xtr_orm_fixtures.bundle import OrmFixturesBundle
from xtr_orm_fixtures.purger import OrmPurgerFactory, PurgerFactoryInterface

pytestmark = pytest.mark.anyio


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(OrmFixturesBundle)


async def test_the_default_connection_gets_the_definitions_its_bind_key_registers() -> None:
    kernel = Kernel(
        "xtr_orm_fixtures",
        env="test",
        environ={"DATABASE_URL": "sqlite+aiosqlite://"},
        bundles={OrmBundle: {"all": True}, OrmFixturesBundle: {"all": True}},
        resources=(),
    )

    async with await kernel.boot() as booted:
        tables = await booted.container.get(TableDefinitions)
        purger_factory = await booted.container.get(PurgerFactoryInterface, "default")

    assert tables.for_connection("default") is not None
    assert isinstance(purger_factory, OrmPurgerFactory)
