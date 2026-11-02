from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from xtr_messenger import (
    Dsn,
    Envelope,
    HandlersLocator,
    MessageBusConfig,
    MessageBusFactory,
    PublisherClosingInterface,
    TransportConfig,
    UnknownTransportOptionError,
    WorkerFactory,
    WorkerInterface,
)
from xtr_orm import ConnectionRegistry
from xtr_orm.database import DatabaseManager
from xtr_orm.exception import SessionUnavailableError
from xtr_orm.migrations import MigrationsConfig, Migrator

from tests.support.messages import OrderPlaced
from tests.support.serializer import SERIALIZER
from xtr_orm_messenger import InvalidOrmDsnError
from xtr_orm_messenger.transport import OrmTransport, OrmTransportFactory

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncEngine
    from xtr_clock import MockClock

pytestmark = pytest.mark.anyio


def _registry(
    engine: AsyncEngine,
    database_url: str,
    session: Callable[[], Awaitable[AsyncSession]] | None = None,
    name: str = "default",
) -> ConnectionRegistry:
    registry = ConnectionRegistry(name)
    registry.register(
        name,
        engine=engine,
        migrator=Migrator(engine, MigrationsConfig()),
        database=DatabaseManager(database_url),
        session=session,
    )
    return registry


def _factory(engine: AsyncEngine, database_url: str, clock: MockClock) -> OrmTransportFactory:
    return OrmTransportFactory(_registry(engine, database_url), SERIALIZER, clock=clock)


async def test_it_serves_the_orm_scheme_only(
    engine: AsyncEngine, database_url: str, clock: MockClock
) -> None:
    factory = _factory(engine, database_url, clock)

    assert factory.supports(Dsn.parse("orm://default"))
    assert not factory.supports(Dsn.parse("sync://"))
    assert isinstance(factory, PublisherClosingInterface)


async def test_one_transport_per_name_is_built_and_kept(
    engine: AsyncEngine, database_url: str, clock: MockClock
) -> None:
    factory = _factory(engine, database_url, clock)
    config = TransportConfig("orm://default", queue="orders")

    first = factory.create({"orders": config})["orders"]

    assert isinstance(first, OrmTransport)
    assert factory.create({"orders": config})["orders"] is first
    assert first.name == "orders"
    assert first.connection.options.queue == "orders"


async def test_settings_reach_the_transport_from_the_dsn_and_the_options(
    engine: AsyncEngine, database_url: str, clock: MockClock
) -> None:
    factory = _factory(engine, database_url, clock)

    built = factory.transport(
        "jobs",
        TransportConfig(
            "orm://default?table_name=jobs&redeliver_timeout=30", options={"poll_interval": "5"}
        ),
    )

    options = built.connection.options
    assert (options.table_name, options.redeliver_timeout, options.poll_interval) == ("jobs", 30, 5)


async def test_a_dsn_naming_no_connection_uses_the_default_one(
    engine: AsyncEngine, database_url: str, clock: MockClock
) -> None:
    factory = OrmTransportFactory(
        _registry(engine, database_url, name="main"), SERIALIZER, clock=clock
    )

    built = factory.transport("orders", TransportConfig("orm://"))

    assert isinstance(built, OrmTransport)


async def test_a_dsn_naming_a_connection_nobody_configured_is_refused(
    engine: AsyncEngine, database_url: str, clock: MockClock
) -> None:
    factory = _factory(engine, database_url, clock)

    with pytest.raises(InvalidOrmDsnError) as refusal:
        _ = factory.transport("orders", TransportConfig("orm://reports"))

    assert (refusal.value.transport, refusal.value.connection, refusal.value.known) == (
        "orders",
        "reports",
        ("default",),
    )
    assert str(refusal.value) == (
        'The "orders" transport names the connection "reports", which is not configured; '
        'the connections are: "default".'
    )


async def test_an_unknown_setting_is_refused(
    engine: AsyncEngine, database_url: str, clock: MockClock
) -> None:
    factory = _factory(engine, database_url, clock)

    with pytest.raises(UnknownTransportOptionError):
        _ = factory.transport("orders", TransportConfig("orm://default?exchange=x"))


async def test_a_bus_sends_and_a_worker_handles_through_the_table(
    engine: AsyncEngine, database_url: str, clock: MockClock
) -> None:
    handled: list[OrderPlaced] = []
    workers: list[WorkerInterface] = []

    async def handle(message: OrderPlaced) -> None:
        handled.append(message)
        workers[0].stop()

    handlers = HandlersLocator()
    _ = handlers.register(OrderPlaced, handle)
    factory = _factory(engine, database_url, clock)
    config = MessageBusConfig(
        transports={"orders": TransportConfig("orm://default")},
        routing={OrderPlaced: "orders"},
    )

    _ = (
        await MessageBusFactory(config, [factory], handlers)
        .bus()
        .dispatch(Envelope(OrderPlaced("o-1")))
    )
    worker = WorkerFactory(config, [factory], handlers).worker(["orders"])
    workers.append(worker)
    await worker.run()

    transport = factory.transport("orders", config.transports["orders"])
    assert handled == [OrderPlaced("o-1")]
    assert await transport.count() == 0
    await factory.close_publishers()


async def test_a_transactional_transport_sends_in_the_unit_of_work(
    engine: AsyncEngine, database_url: str, clock: MockClock
) -> None:
    sessions = async_sessionmaker(engine)
    opened: list[AsyncSession] = []

    async def unit_session() -> AsyncSession:
        if not opened:
            raise SessionUnavailableError("default", "no unit of work is under way")
        return opened[0]

    factory = OrmTransportFactory(
        _registry(engine, database_url, unit_session), SERIALIZER, clock=clock
    )
    transport = factory.transport("orders", TransportConfig("orm://default?transactional=true"))

    async with sessions() as session:
        opened.append(session)
        _ = await transport.send(Envelope(OrderPlaced("o-1")))
        assert await transport.count() == 0
        await session.commit()
    opened.clear()
    _ = await transport.send(Envelope(OrderPlaced("o-2")))

    assert [envelope.message async for envelope in transport.all()] == [
        OrderPlaced("o-1"),
        OrderPlaced("o-2"),
    ]
