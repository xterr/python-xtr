"""Unit tests for ``orm:fixtures:load``."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final, override

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from xtr_console import Application, ApplicationTester, CommandInvokerInterface, ExitCode
from xtr_orm import ConnectionRegistry, DatabaseManager, MigrationsConfig, Migrator

from tests.support.locators import locator
from tests.support.models import Base, Group, User
from tests.support.seeds import (
    GroupFixture,
    NumberedFixture,
    UserFixture,
    create_database,
    names,
)
from xtr_orm_fixtures import DependentFixtureInterface, Fixture, FixtureInterface, TableDefinitions
from xtr_orm_fixtures.command import LoadDataFixturesCommand
from xtr_orm_fixtures.purger import OrmPurgerFactory, PurgerFactoryInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence

    from sqlalchemy import MetaData
    from sqlalchemy.ext.asyncio import AsyncEngine
    from xtr_console.command import CommandArguments, CommandDescriptor, CommandSignature

    from xtr_orm_fixtures.purger import PurgerInterface

pytestmark = pytest.mark.anyio


@final
class RecordingPurgerFactory(PurgerFactoryInterface):
    """Builds the default purger, keeping what each call asked for."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], bool]] = []

    @override
    def create_for_connection(
        self,
        connection: str,
        metadata: MetaData | Sequence[MetaData],
        *,
        excluded: Iterable[str] = (),
        purge_with_truncate: bool = False,
    ) -> PurgerInterface:
        excluded = tuple(excluded)
        self.calls.append((connection, excluded, purge_with_truncate))
        return OrmPurgerFactory().create_for_connection(
            connection, metadata, excluded=excluded, purge_with_truncate=purge_with_truncate
        )


@final
class _Invoker(CommandInvokerInterface):
    """Builds the command with its services and hands it the fixtures, as a container would."""

    def __init__(self, command: LoadDataFixturesCommand, fixtures: list[FixtureInterface]) -> None:
        self._command = command
        self._fixtures = fixtures

    @override
    async def invoke(
        self,
        command: CommandDescriptor,
        signature: CommandSignature,
        arguments: CommandArguments,
    ) -> object:
        del command, signature
        found = locator(
            FixtureInterface,
            {f"{type(each).__module__}.{type(each).__qualname__}": each for each in self._fixtures},
        )
        # The arguments come parsed off the command line, typed only as objects.
        call = cast("Callable[..., Awaitable[object]]", self._command)
        return await call(*arguments.args, fixtures=found, **arguments.kwargs)


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    await create_database(engine)
    async with AsyncSession(engine) as opened:
        yield opened


@pytest.fixture
def connections(
    engine: AsyncEngine, session: AsyncSession, database_url: str
) -> ConnectionRegistry:
    async def current() -> AsyncSession:
        return session

    registry = ConnectionRegistry()
    registry.register(
        "default",
        engine=engine,
        migrator=Migrator(engine, MigrationsConfig(), Base.metadata),
        database=DatabaseManager(database_url),
        session=current,
    )
    return registry


@pytest.fixture
def purger_factory() -> RecordingPurgerFactory:
    return RecordingPurgerFactory()


@pytest.fixture
def fixtures() -> list[FixtureInterface]:
    return [UserFixture(), GroupFixture()]


def _tester(
    connections: ConnectionRegistry,
    fixtures: list[FixtureInterface],
    purger_factory: PurgerFactoryInterface,
    tables: TableDefinitions | None = None,
) -> ApplicationTester:
    command = LoadDataFixturesCommand(
        connections,
        tables or TableDefinitions({"default": Base.metadata}),
        locator(PurgerFactoryInterface, {"default": purger_factory, "mine": OrmPurgerFactory()}),
    )
    application = Application("test", catch_exceptions=False)
    application.use_invoker(_Invoker(command, fixtures))
    return ApplicationTester(application, width=200)


@pytest.fixture
def tester(
    connections: ConnectionRegistry,
    fixtures: list[FixtureInterface],
    purger_factory: RecordingPurgerFactory,
) -> ApplicationTester:
    return _tester(connections, fixtures, purger_factory)


def _output(tester: ApplicationTester) -> str:
    return " ".join((tester.display + tester.error_display).split())


async def _rows(engine: AsyncEngine) -> tuple[list[str], list[str]]:
    return await names(engine, Group), await names(engine, User)


async def test_loads_after_confirmation(tester: ApplicationTester, engine: AsyncEngine) -> None:
    assert await tester.execute(["orm:fixtures:load"], inputs=["y"]) == ExitCode.SUCCESS

    assert 'Careful, database "' in _output(tester)
    assert "Loaded 2 fixtures." in _output(tester)
    assert await _rows(engine) == (["staff"], ["ada"])


async def test_declining_exits_successfully_and_changes_nothing(
    tester: ApplicationTester, engine: AsyncEngine
) -> None:
    assert await tester.execute(["orm:fixtures:load"], inputs=["n"]) == ExitCode.SUCCESS

    assert "Loaded" not in _output(tester)
    assert await _rows(engine) == (["old"], [])


async def test_non_interactive_proceeds(tester: ApplicationTester, engine: AsyncEngine) -> None:
    assert await tester.execute(["orm:fixtures:load"], interactive=False) == ExitCode.SUCCESS

    assert await _rows(engine) == (["staff"], ["ada"])


async def test_append_skips_confirmation_and_purge(
    tester: ApplicationTester, engine: AsyncEngine
) -> None:
    assert await tester.execute(["orm:fixtures:load", "--append"]) == ExitCode.SUCCESS

    assert "Careful" not in _output(tester)
    assert "purging database" not in _output(tester)
    assert await _rows(engine) == (["old", "staff"], ["ada"])


async def test_dry_run_changes_nothing_and_says_so(
    tester: ApplicationTester, engine: AsyncEngine
) -> None:
    assert await tester.execute(["orm:fixtures:load", "--dry-run"]) == ExitCode.SUCCESS

    assert "Careful" not in _output(tester)
    assert "(dry-run)" in _output(tester)
    assert "Loaded 2 fixtures and rolled them back." in _output(tester)
    assert await _rows(engine) == (["old"], [])


async def test_group_option_repeats(
    connections: ConnectionRegistry, purger_factory: RecordingPurgerFactory, engine: AsyncEngine
) -> None:
    tester = _tester(
        connections, [UserFixture(), GroupFixture(), NumberedFixture()], purger_factory
    )

    argv = [
        "orm:fixtures:load",
        "--append",
        "--group",
        "NumberedFixture",
        "--group",
        "GroupFixture",
    ]
    assert await tester.execute(argv) == ExitCode.SUCCESS

    assert "Loaded 2 fixtures." in _output(tester)
    assert await _rows(engine) == (["old", "staff"], [])


async def test_no_fixtures_is_an_error_naming_the_groups(tester: ApplicationTester) -> None:
    argv = ["orm:fixtures:load", "--append", "--group", "nowhere", "--group", "none"]

    assert await tester.execute(argv) == ExitCode.FAILURE

    assert "Could not find any fixture services to load in the groups (nowhere, none)." in (
        _output(tester)
    )


async def test_no_fixtures_at_all_is_an_error(
    connections: ConnectionRegistry, purger_factory: RecordingPurgerFactory
) -> None:
    tester = _tester(connections, [], purger_factory)

    assert await tester.execute(["orm:fixtures:load", "--append"]) == ExitCode.FAILURE

    assert "Could not find any fixture services to load." in _output(tester)


async def test_unknown_purger_is_invalid(tester: ApplicationTester, engine: AsyncEngine) -> None:
    argv = ["orm:fixtures:load", "--dry-run", "--purger", "other"]

    assert await tester.execute(argv) == ExitCode.INVALID

    assert 'No purger factory is named "other"; the purger factories are: default, mine.' in (
        _output(tester)
    )
    assert await _rows(engine) == (["old"], [])


async def test_a_purger_is_picked_by_name(
    tester: ApplicationTester, purger_factory: RecordingPurgerFactory, engine: AsyncEngine
) -> None:
    argv = ["orm:fixtures:load", "--purger", "mine"]

    assert await tester.execute(argv, interactive=False) == ExitCode.SUCCESS

    assert purger_factory.calls == []
    assert await _rows(engine) == (["staff"], ["ada"])


async def test_purge_exclusions_and_truncate_reach_the_factory(
    tester: ApplicationTester, purger_factory: RecordingPurgerFactory, engine: AsyncEngine
) -> None:
    argv = [
        "orm:fixtures:load",
        "--purge-exclusions",
        "groups",
        "--purge-exclusions",
        "tags",
        "--purge-with-truncate",
    ]

    assert await tester.execute(argv, interactive=False) == ExitCode.SUCCESS

    assert purger_factory.calls == [("default", ("groups", "tags"), True)]
    assert await _rows(engine) == (["old", "staff"], ["ada"])


async def test_unknown_connection_fails(tester: ApplicationTester) -> None:
    argv = ["orm:fixtures:load", "--connection", "reports"]

    assert await tester.execute(argv) == ExitCode.FAILURE

    assert "reports" in _output(tester)
    assert "default" in _output(tester)


async def test_a_connection_without_table_definitions_is_invalid(
    connections: ConnectionRegistry, purger_factory: RecordingPurgerFactory, engine: AsyncEngine
) -> None:
    tester = _tester(connections, [GroupFixture()], purger_factory, TableDefinitions({}))

    assert await tester.execute(["orm:fixtures:load", "--dry-run"]) == ExitCode.INVALID

    assert 'No connection is named "default"' in _output(tester)
    assert await _rows(engine) == (["old"], [])


async def test_definitions_are_not_needed_to_append(
    connections: ConnectionRegistry, purger_factory: RecordingPurgerFactory, engine: AsyncEngine
) -> None:
    tester = _tester(connections, [GroupFixture()], purger_factory, TableDefinitions({}))

    assert await tester.execute(["orm:fixtures:load", "--append"]) == ExitCode.SUCCESS

    assert await _rows(engine) == (["old", "staff"], [])


async def test_a_connection_without_a_session_fails(
    engine: AsyncEngine, database_url: str, purger_factory: RecordingPurgerFactory
) -> None:
    registry = ConnectionRegistry()
    registry.register(
        "default",
        engine=engine,
        migrator=Migrator(engine, MigrationsConfig(), Base.metadata),
        database=DatabaseManager(database_url),
    )
    tester = _tester(registry, [GroupFixture()], purger_factory)

    assert await tester.execute(["orm:fixtures:load", "--append"]) == ExitCode.FAILURE

    assert "registered without a session" in _output(tester)


@final
class Ping(Fixture, DependentFixtureInterface):
    @override
    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        return (Pong,)

    @override
    async def load(self, session: AsyncSession) -> None:
        del session


@final
class Pong(Fixture, DependentFixtureInterface):
    @override
    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        return (Ping,)

    @override
    async def load(self, session: AsyncSession) -> None:
        del session


async def test_cycle_is_reported(
    connections: ConnectionRegistry, purger_factory: RecordingPurgerFactory, engine: AsyncEngine
) -> None:
    tester = _tester(connections, [Ping(), Pong()], purger_factory)

    assert await tester.execute(["orm:fixtures:load", "--append"]) == ExitCode.FAILURE

    assert "Ping" in _output(tester)
    assert "Pong" in _output(tester)
    assert await _rows(engine) == (["old"], [])


async def test_each_fixture_is_logged_to_the_console(tester: ApplicationTester) -> None:
    assert await tester.execute(["orm:fixtures:load", "--dry-run"]) == ExitCode.SUCCESS

    lines = [line.strip() for line in tester.display.splitlines() if "> " in line]
    assert lines == [
        "> purging database",
        "> loading tests.support.seeds.GroupFixture",
        "> loading tests.support.seeds.UserFixture",
    ]


async def test_help_documents_every_option_with_an_example(tester: ApplicationTester) -> None:
    assert await tester.execute(["orm:fixtures:load", "--help"]) == ExitCode.SUCCESS

    shown = _output(tester)
    for example in (
        "--append",
        "--dry-run",
        "--group demo",
        "--connection audit",
        "--purger mine",
        "--purge-exclusions countries",
        "--purge-with-truncate",
    ):
        assert f"Example: {example}" in shown
