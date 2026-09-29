"""The database: one connection, its URL from the environment, its revisions in migrations/.

The models are advanced-alchemy's (``ordering/order.py``), so the table definitions a diff
compares with are the ones advanced-alchemy registers — nothing to name here. The URL is read
when a connection is first used — a command that never touches the database never reads it —
and its query's engine and session options are merged over the ones below.

Every environment runs the same revisions: ``orm:migrations:migrate`` brings a database to
the latest, ``orm:migrations:status`` says where one stands.
"""

from __future__ import annotations

from xtr_dependency_injection import configure, env
from xtr_orm.bundle import ConnectionConfig, MigrationsConfig, OrmConfig

__all__ = ["orm"]


@configure
def orm() -> OrmConfig:
    """``SHOP_DATABASE_URL`` — a SQLite file per environment in dev and test, PostgreSQL in prod."""
    return OrmConfig(
        connections={
            "default": ConnectionConfig(
                url=env("resolve:SHOP_DATABASE_URL"),
                engine_options={"echo": False},
                session_options={"expire_on_commit": True},
                migrations=MigrationsConfig(
                    directory="%kernel.project_dir%/migrations",
                    # SQLite alters a table by copying it: write every change that way.
                    render_as_batch=True,
                ),
            ),
        },
    )
