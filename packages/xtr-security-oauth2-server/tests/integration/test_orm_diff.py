"""The revision a database writes for this package's tables, column types included.

The package ships the mapping, not the revisions: an application generates its
own from the tables the driver builds. That only works if a diff can render
every column — a custom column type has to come out as an expression the
revision file can import — so the check is on the written file, not on the
database. An application owning its client class has the same right to one
revision: its own table and the credential tables pointing at it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import anyio
import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import create_async_engine
from xtr_orm import MigrationsConfig, Migrator

from tests.support.app_client import PlainAppClient
from tests.support.orm import orm_driver

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_security_oauth2_server.persistence.mapping.driver import Driver

pytestmark = pytest.mark.anyio

_TYPES: Final = "xtr_security_oauth2_server.persistence.type"


async def _written(tmp_path: Path, driver: Driver, metadata: MetaData | None = None) -> str:
    """Return the body of the revision a fresh database writes for ``driver``."""
    definitions = metadata if metadata is not None else MetaData()
    _ = driver.load_metadata(definitions)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'app.sqlite'}")
    try:
        migrator = Migrator(
            engine,
            MigrationsConfig(directory=str(tmp_path / "migrations"), render_as_batch=True),
            definitions,
        )
        revision = await migrator.diff("the oauth2 server tables")
        assert revision is not None

        return await anyio.Path(revision.path).read_text(encoding="utf-8")
    finally:
        await engine.dispose()
        driver._dispose()


async def test_a_diff_creates_every_table_the_driver_mapped(tmp_path: Path) -> None:
    body = await _written(tmp_path, orm_driver())

    for table in (
        "oauth2_client",
        "oauth2_access_token",
        "oauth2_authorization_code",
        "oauth2_refresh_token",
        "oauth2_device_code",
    ):
        assert f"op.create_table('{table}'" in body


async def test_a_diff_leaves_out_the_tables_the_deployment_turned_off(tmp_path: Path) -> None:
    body = await _written(
        tmp_path,
        orm_driver(persist_access_token=False, enable_device_code_grant=False),
    )

    assert "op.create_table('oauth2_access_token'" not in body
    assert "op.create_table('oauth2_device_code'" not in body
    assert "op.create_table('oauth2_authorization_code'" in body


async def test_a_diff_renders_what_a_credential_points_at(tmp_path: Path) -> None:
    body = await _written(tmp_path, orm_driver())

    assert "ForeignKeyConstraint(['client'], ['oauth2_client.identifier']" in body
    assert "ForeignKeyConstraint(['access_token'], ['oauth2_access_token.identifier']" in body
    assert "ondelete='CASCADE'" in body
    assert "ondelete='SET NULL'" in body


async def test_a_diff_renders_an_application_client_and_what_points_at_it(
    tmp_path: Path,
) -> None:
    body = await _written(
        tmp_path,
        orm_driver(client_class=PlainAppClient),
        PlainAppClient.metadata,
    )

    assert "op.create_table('app_client'" in body
    assert "op.create_table('oauth2_access_token'" in body
    assert "op.create_table('oauth2_refresh_token'" in body
    assert "ForeignKeyConstraint(['client'], ['app_client.identifier']" in body
    assert "op.create_table('oauth2_client'" not in body


@pytest.mark.parametrize(
    "rendered",
    [
        f"{_TYPES}.grant.Grant()",
        f"{_TYPES}.redirect_uri.RedirectUri()",
        f"{_TYPES}.scope.Scope()",
        f"{_TYPES}.utc_datetime.UtcDateTime()",
    ],
)
async def test_every_custom_column_type_is_rendered_as_itself(
    tmp_path: Path, rendered: str
) -> None:
    body = await _written(tmp_path, orm_driver())

    assert rendered in body


@pytest.mark.parametrize(
    "module",
    [
        f"{_TYPES}.grant",
        f"{_TYPES}.redirect_uri",
        f"{_TYPES}.scope",
        f"{_TYPES}.utc_datetime",
    ],
)
async def test_the_revision_imports_the_module_of_every_type_it_names(
    tmp_path: Path, module: str
) -> None:
    body = await _written(tmp_path, orm_driver())

    assert f"import {module}" in body
