"""One SQLite database; orders queued in a table on it, the table in its migrations."""

from __future__ import annotations

from xtr_dependency_injection import configure, env
from xtr_messenger import MessageBusConfig, TransportConfig
from xtr_orm.bundle import ConnectionConfig, MigrationsConfig, OrmConfig

from xtr_orm_messenger.bundle import OrmMessengerConfig

from .messages import QueuedOrder

BIND_KEY = "xtr_orm_messenger_test_app"
"""Where the registered definitions live; its own, so no other test's tables join them."""


@configure
def orm() -> OrmConfig:
    return OrmConfig(
        connections={
            "default": ConnectionConfig(
                url=env("ORM_TEST_URL"),
                bind_key=BIND_KEY,
                migrations=MigrationsConfig(
                    directory=env("ORM_TEST_MIGRATIONS"), render_as_batch=True
                ),
            ),
        },
    )


@configure
def messenger() -> MessageBusConfig:
    return MessageBusConfig(
        transports={"orders": TransportConfig("orm://default?poll_interval=0.05")},
        routing={QueuedOrder: "orders"},
    )


@configure
def orm_messenger() -> OrmMessengerConfig:
    return OrmMessengerConfig(migrations_connection="default")
