"""``orm:fixtures:load``: empty a database and load the application's fixtures into it."""

from __future__ import annotations

from typing import final, override

from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import Injected, ServiceLocator
from xtr_logging_contracts import AbstractLogger, Context, LevelLike
from xtr_orm import ConnectionRegistry
from xtr_orm.exception import SessionUnavailableError, UnknownConnectionError

from xtr_orm_fixtures.exception import OrmFixturesError
from xtr_orm_fixtures.executor import AbstractExecutor, DryRunOrmExecutor, OrmExecutor
from xtr_orm_fixtures.fixture_interface import FixtureInterface
from xtr_orm_fixtures.loader import Loader
from xtr_orm_fixtures.purger import PurgerFactoryInterface, PurgerInterface
from xtr_orm_fixtures.table_definitions import TableDefinitions

__all__ = ["LoadDataFixturesCommand"]


@as_command("orm:fixtures:load", description="Load data fixtures into the database.")
@final
class LoadDataFixturesCommand:
    """Empties a connection's database, then loads every fixture of the application into it."""

    __slots__ = ("_connections", "_purger_factories", "_tables")

    def __init__(
        self,
        connections: ConnectionRegistry,
        tables: TableDefinitions,
        purger_factories: ServiceLocator[PurgerFactoryInterface],
    ) -> None:
        """Load through ``connections``, emptying the tables ``tables`` names.

        Args:
            connections: The connections fixtures may load into.
            tables: The table definitions of each connection: what is emptied.
            purger_factories: What builds the purger, by the name ``--purger`` gives.
        """
        self._connections = connections
        self._tables = tables
        self._purger_factories = purger_factories

    async def __call__(  # noqa: PLR0911 — one early exit per way a run is refused
        self,
        io: ConsoleStyle,
        fixtures: Injected[ServiceLocator[FixtureInterface]],
        *,
        append: bool = False,
        dry_run: bool = False,
        group: list[str] | None = None,
        connection: str | None = None,
        purger: str = "default",
        purge_exclusions: list[str] | None = None,
        purge_with_truncate: bool = False,
    ) -> int:
        """Load data fixtures into the database.

        Every table the connection maps is emptied first, a referencing table
        before the one it references, after you confirm; then every fixture
        loads, all in one transaction. Fixtures are found wherever the
        application keeps them.

        Args:
            io: Where the command reads and writes.
            fixtures: Every fixture of the application, by name.
            append: Add to what the database holds instead of emptying it
                first; nothing is asked. Example: --append.
            dry_run: Run everything, the emptying included, then roll it all
                back; nothing is asked. Example: --dry-run.
            group: Load only the fixtures of this group, and those they
                depend on; repeat for several. A fixture is also in the group
                named after its class. Example: --group demo.
            connection: The connection to load into; the default one when
                left out. Example: --connection audit.
            purger: The purger factory to empty the database with, by name.
                Example: --purger mine.
            purge_exclusions: A table to leave as it is, by name or
                schema-qualified name; repeat for several. Example:
                --purge-exclusions countries.
            purge_with_truncate: Empty the tables with TRUNCATE rather than
                DELETE. Example: --purge-with-truncate.
        """
        name = connection or self._connections.default
        if not self._connections.has(name):
            unknown = UnknownConnectionError(name, self._connections.names())
            io.error(escape(str(unknown)))
            return ExitCode.FAILURE
        if not (append or dry_run) and not await self._confirmed(io, name):
            return ExitCode.SUCCESS

        groups = tuple(group or ())
        try:
            ordered = await _ordered(fixtures, groups)
        except OrmFixturesError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        if not ordered:
            where = f" in the groups ({', '.join(groups)})" if groups else ""
            io.error(escape(f"Could not find any fixture services to load{where}."))
            return ExitCode.FAILURE

        if purger not in self._purger_factories:
            known = ", ".join(str(alias) for alias in self._purger_factories.provided_services())
            io.error(
                escape(f'No purger factory is named "{purger}"; the purger factories are: {known}.')
            )
            return ExitCode.INVALID
        emptying: PurgerInterface | None = None
        if not append:
            try:
                definitions = self._tables.for_connection(name)
            except OrmFixturesError as error:
                io.error(escape(str(error)))
                return ExitCode.INVALID
            factory = await self._purger_factories.get(purger)
            emptying = factory.create_for_connection(
                name,
                definitions,
                excluded=tuple(purge_exclusions or ()),
                purge_with_truncate=purge_with_truncate,
            )

        try:
            session = await self._connections.session(name)
        except SessionUnavailableError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        if dry_run:
            io.text("  (dry-run)")
        executor_type: type[AbstractExecutor] = DryRunOrmExecutor if dry_run else OrmExecutor
        await executor_type(session, emptying, _ConsoleLogger(io)).execute(ordered, append=append)

        loaded = f"Loaded {len(ordered)} fixture{'' if len(ordered) == 1 else 's'}"
        io.success(f"{loaded} and rolled them back." if dry_run else f"{loaded}.")
        return ExitCode.SUCCESS

    async def _confirmed(self, io: ConsoleStyle, name: str) -> bool:
        """Ask before emptying; a run nobody can answer goes ahead."""
        database = (await self._connections.engine(name)).url.database or name
        return io.confirm(
            escape(f'Careful, database "{database}" will be purged. Do you want to continue?'),
            default=not io.interactive,
        )


async def _ordered(
    fixtures: ServiceLocator[FixtureInterface], groups: tuple[str, ...]
) -> list[FixtureInterface]:
    """Return the fixtures of ``groups`` — all of them, with none — in the order they load.

    Raises:
        OrmFixturesError: If a fixture is refused, depends on one that is not
            there, or the fixtures depend on one another in a circle.
    """
    loader = Loader()
    loader.add_fixtures([fixture async for _, fixture in fixtures])
    return loader.get_fixtures(groups)


@final
class _ConsoleLogger(AbstractLogger):
    """Writes each message of a run to the console, its placeholders filled in."""

    def __init__(self, io: ConsoleStyle) -> None:
        self._io = io

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        del level
        for key, value in (context or {}).items():
            message = message.replace(f"{{{key}}}", str(value))
        self._io.text(f"  > {escape(message)}")
