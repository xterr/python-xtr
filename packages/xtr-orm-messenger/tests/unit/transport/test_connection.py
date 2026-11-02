from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from xtr_orm.exception import SessionUnavailableError

from tests.support.connections import connection_on
from xtr_orm_messenger.transport import LISTING_PAGE_SIZE, OrmOptions

if TYPE_CHECKING:
    from sqlalchemy import Connection as SyncConnection
    from xtr_clock import MockClock

pytestmark = pytest.mark.anyio

HEADERS = {"type": "tests.message"}


def _naive(text_value: str) -> datetime:
    return datetime.fromisoformat(text_value)


async def _tables(engine: AsyncEngine) -> list[str]:
    def names(connection: SyncConnection) -> list[str]:
        return inspect(connection).get_table_names()

    async with engine.connect() as connection:
        return await connection.run_sync(names)


async def test_a_sent_message_is_claimed_once_and_marked_handed_out(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)
    message_id = await connection.send("{}", HEADERS)

    claimed = await connection.get()

    assert claimed is not None
    assert (claimed.id, claimed.body, dict(claimed.headers), claimed.queue) == (
        message_id,
        "{}",
        HEADERS,
        "default",
    )
    assert claimed.created_at == claimed.available_at == _naive("2026-01-01T00:00:00")
    assert claimed.delivered_at == _naive("2026-01-01T00:00:00")
    assert await connection.get() is None


async def test_messages_are_claimed_oldest_due_first(engine: AsyncEngine, clock: MockClock) -> None:
    connection = connection_on(engine, clock)
    first = await connection.send("1", HEADERS)
    clock.sleep(1)
    second = await connection.send("2", HEADERS)

    claimed = [await connection.get(), await connection.get()]

    assert [message.id for message in claimed if message is not None] == [first, second]


async def test_a_delayed_message_is_due_only_once_its_delay_passed(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)
    _ = await connection.send("{}", HEADERS, delay_ms=2000)

    assert await connection.get() is None
    clock.sleep(2)
    assert await connection.get() is not None


async def test_a_delay_with_a_fraction_of_a_second_is_rounded_up(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)
    message_id = await connection.send("{}", HEADERS, delay_ms=1500)

    stored = await connection.find(message_id)

    assert stored is not None
    assert stored.available_at == _naive("2026-01-01T00:00:02")


async def test_a_delay_of_whole_seconds_is_kept_as_it_is(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)
    message_id = await connection.send("{}", HEADERS, delay_ms=3000)

    stored = await connection.find(message_id)

    assert stored is not None
    assert stored.available_at == _naive("2026-01-01T00:00:03")


async def test_a_message_never_settled_is_handed_out_again_after_the_redeliver_timeout(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock, OrmOptions(redeliver_timeout=60))
    message_id = await connection.send("{}", HEADERS)
    _ = await connection.get()

    clock.sleep(60)
    assert await connection.get() is None
    clock.sleep(1)
    again = await connection.get()

    assert again is not None
    assert again.id == message_id


@pytest.mark.parametrize("settle", ["ack", "reject"])
async def test_settling_a_message_deletes_it(
    engine: AsyncEngine, clock: MockClock, settle: str
) -> None:
    connection = connection_on(engine, clock, OrmOptions(redeliver_timeout=60))
    message_id = await connection.send("{}", HEADERS)
    _ = await connection.get()

    await (connection.ack if settle == "ack" else connection.reject)(message_id)
    clock.sleep(3600)

    assert await connection.find(message_id) is None
    assert await connection.get() is None


async def test_keepalive_restarts_the_redelivery_clock(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock, OrmOptions(redeliver_timeout=60))
    message_id = await connection.send("{}", HEADERS)
    _ = await connection.get()

    clock.sleep(50)
    await connection.keepalive(message_id)
    clock.sleep(50)

    assert await connection.get() is None
    stored = await connection.find(message_id)
    assert stored is not None
    assert stored.delivered_at == _naive("2026-01-01T00:00:50")


async def test_queues_sharing_a_table_never_see_each_other(
    engine: AsyncEngine, clock: MockClock
) -> None:
    high = connection_on(engine, clock, OrmOptions(queue="high"))
    low = connection_on(engine, clock, OrmOptions(queue="low"))
    message_id = await high.send("{}", HEADERS)

    assert await low.get() is None
    assert await low.find(message_id) is None
    assert await low.count() == 0
    assert await high.count() == 1


async def test_find_returns_a_handed_out_message_too(engine: AsyncEngine, clock: MockClock) -> None:
    connection = connection_on(engine, clock)
    message_id = await connection.send("{}", HEADERS)
    _ = await connection.get()

    stored = await connection.find(message_id)

    assert stored is not None
    assert stored.delivered_at is not None


async def test_count_and_all_see_only_what_a_worker_could_claim_now(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)
    handed_out = await connection.send("handed out", HEADERS)
    _ = await connection.send("later", HEADERS, delay_ms=60_000)
    waiting = await connection.send("waiting", HEADERS)
    claimed = await connection.get()

    listed = [message.id async for message in connection.all()]

    assert claimed is not None
    assert claimed.id == handed_out
    assert await connection.count() == 1
    assert listed == [waiting]


async def test_all_honours_its_limit(engine: AsyncEngine, clock: MockClock) -> None:
    connection = connection_on(engine, clock)
    sent = [await connection.send(str(n), HEADERS) for n in range(5)]

    listed = [message.id async for message in connection.all(limit=3)]

    assert listed == sent[:3]


async def test_all_lists_every_message_page_by_page(engine: AsyncEngine, clock: MockClock) -> None:
    connection = connection_on(engine, clock)
    total = LISTING_PAGE_SIZE * 2 + 5
    sent = [await connection.send(str(n), HEADERS) for n in range(total)]

    listed = [message.id async for message in connection.all()]
    limited = [message.id async for message in connection.all(limit=LISTING_PAGE_SIZE + 3)]

    assert listed == sent
    assert limited == sent[: LISTING_PAGE_SIZE + 3]


async def test_all_ends_on_a_page_that_comes_out_exactly_full(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)
    sent = [await connection.send(str(n), HEADERS) for n in range(LISTING_PAGE_SIZE)]

    listed = [message.id async for message in connection.all()]

    assert listed == sent


async def test_the_first_statement_creates_the_missing_table(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)

    assert await connection.get() is None
    assert await _tables(engine) == ["messenger_messages"]


async def test_setup_leaves_an_existing_table_as_it_is(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)
    message_id = await connection.send("{}", HEADERS)

    await connection.setup()

    assert await connection.find(message_id) is not None


async def test_without_auto_setup_a_missing_table_is_the_databases_error(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock, OrmOptions(auto_setup=False))

    with pytest.raises(DBAPIError):
        _ = await connection.get()

    assert await _tables(engine) == []


async def test_another_error_is_raised_as_it_came(engine: AsyncEngine, clock: MockClock) -> None:
    connection = connection_on(engine, clock)
    await connection.setup()
    async with engine.begin() as raw:
        _ = await raw.execute(text("DROP TABLE messenger_messages"))
        _ = await raw.execute(text("CREATE TABLE messenger_messages (id INTEGER PRIMARY KEY)"))

    with pytest.raises(DBAPIError):
        _ = await connection.get()


async def test_the_table_is_named_by_its_option(engine: AsyncEngine, clock: MockClock) -> None:
    connection = connection_on(engine, clock, OrmOptions(table_name="jobs"))

    _ = await connection.send("{}", HEADERS)

    assert connection.table.name == "jobs"
    assert await _tables(engine) == ["jobs"]


async def test_ping_tells_whether_the_database_answers(
    engine: AsyncEngine, clock: MockClock, tmp_path_factory: pytest.TempPathFactory
) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415 — this test only

    unreachable = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path_factory.mktemp('gone') / 'missing' / 'db.sqlite'}"
    )
    try:
        assert await connection_on(engine, clock).ping()
        assert not await connection_on(unreachable, clock).ping()
    finally:
        await unreachable.dispose()


async def test_off_postgresql_a_worker_waits_its_poll_interval(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock, OrmOptions(poll_interval=2.5))

    await connection.wait()
    await connection.wait()
    await connection.close()

    assert clock.now().isoformat() == "2026-01-01T00:00:05+00:00"


async def test_without_use_notify_a_worker_waits_its_poll_interval(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock, OrmOptions(use_notify=False, poll_interval=1))

    await connection.wait()

    assert clock.now().isoformat() == "2026-01-01T00:00:01+00:00"


async def test_transactional_sends_commit_with_the_unit_of_work(
    engine: AsyncEngine, clock: MockClock
) -> None:
    sessions = async_sessionmaker(engine)
    async with sessions() as session:

        async def unit_session() -> AsyncSession:
            return session

        connection = connection_on(
            engine, clock, OrmOptions(transactional=True), session_factory=unit_session
        )
        message_id = await connection.send("{}", HEADERS)
        assert await connection.count() == 0
        await session.commit()

    assert await connection.find(message_id) is not None


async def test_transactional_sends_roll_back_with_the_unit_of_work(
    engine: AsyncEngine, clock: MockClock
) -> None:
    sessions = async_sessionmaker(engine)
    async with sessions() as session:

        async def unit_session() -> AsyncSession:
            return session

        connection = connection_on(
            engine, clock, OrmOptions(transactional=True), session_factory=unit_session
        )
        _ = await connection.send("{}", HEADERS)
        await session.rollback()

    assert await connection.count() == 0


async def test_transactional_sends_outside_a_unit_of_work_commit_at_once(
    engine: AsyncEngine, clock: MockClock
) -> None:
    async def no_unit() -> AsyncSession:
        raise SessionUnavailableError("default", "no unit of work is under way")

    connection = connection_on(
        engine, clock, OrmOptions(transactional=True), session_factory=no_unit
    )

    _ = await connection.send("{}", HEADERS)

    assert await connection.count() == 1


async def test_a_session_is_not_asked_for_unless_sends_are_transactional(
    engine: AsyncEngine, clock: MockClock
) -> None:
    async def refuses() -> AsyncSession:
        pytest.fail("the unit's session was asked for")

    connection = connection_on(engine, clock, session_factory=refuses)

    _ = await connection.send("{}", HEADERS)

    async with engine.connect() as raw:
        rows = (await raw.execute(select(connection.table.c.body))).all()
    assert len(rows) == 1
