"""``make:migration``: a revision bringing the database to the table definitions."""

from __future__ import annotations

from typing import Final, final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_orm import ConnectionRegistry, MigrationError, UnknownConnectionError

from xtr_maker.exception import UnsafePathError
from xtr_maker.file_manager import (  # noqa: TC001 — the container reads annotations at runtime.
    FileManager,
)

__all__ = ["MakeMigrationCommand"]

_DEFAULT_MESSAGE: Final = "auto"
"""The message a revision is written with when none is given."""

_MIGRATE_FIRST: Final = "Run orm:migrations:migrate -n first."


@final
@as_command(
    "make:migration",
    description="Write a revision bringing the database to the table definitions.",
)
class MakeMigrationCommand:
    """Compares a connection's database with its table definitions, and writes what differs.

    The revision is written by the connection's migrator, into its migrations
    directory, exactly as ``orm:migrations:diff`` writes one; nothing is
    written when nothing differs. The database must have every revision
    applied first, or the comparison would see what is still to run rather
    than what the table definitions add.
    """

    __slots__ = ("_connections", "_file_manager")

    def __init__(self, connections: ConnectionRegistry, file_manager: FileManager) -> None:
        """Compare the databases ``connections`` names, reporting paths inside ``file_manager``'s.

        Args:
            connections: Every connection, each with its migrator.
            file_manager: The project the written revision's path is shown from.
        """
        self._connections = connections
        self._file_manager = file_manager

    async def __call__(
        self,
        io: ConsoleStyle,
        *,
        message: str | None = None,
        connection: str | None = None,
    ) -> int:
        """Write a revision of what differs between the database and the table definitions.

        Args:
            io: Where the command writes, and asks.
            message: What the revision does; it names the file too. Asked
                when left out, defaulting to ``auto``.
            connection: The connection to compare; the default one when left
                out.
        """
        if not self._connections.has(connection):
            unknown = UnknownConnectionError(
                connection or self._connections.default, self._connections.names()
            )
            io.error(escape(str(unknown)))
            return ExitCode.INVALID
        typed = (
            message if message is not None else io.ask("The revision's message", _DEFAULT_MESSAGE)
        )
        described = typed.strip()
        if not described:
            io.error("The revision's message cannot be empty.")
            return ExitCode.INVALID
        migrator = await self._connections.migrator(connection)
        try:
            # Read before comparing: a database behind its revisions cannot be
            # compared with the table definitions, and telling it apart up front
            # names the fix.
            pending = len((await migrator.status()).new)
            if pending:
                io.error(_behind(pending))
                io.text(_MIGRATE_FIRST)
                return ExitCode.FAILURE
            written = await migrator.diff(described)
        except MigrationError as error:
            io.error(escape(error.reason))
            return ExitCode.FAILURE
        if written is None:
            io.note("No database changes were detected.")
            return ExitCode.SUCCESS
        io.text(f" [green]created[/]: {escape(self._shown(written.path))}")
        io.success(f"Wrote the revision {escape(written.version)}.")
        io.text("Next:")
        io.text("  - Review the new revision, then run orm:migrations:migrate -n.")
        return ExitCode.SUCCESS

    def _shown(self, path: str) -> str:
        """Return ``path`` relative to the project, or as it is when it lies outside it."""
        try:
            return self._file_manager.relative(path)
        except UnsafePathError:
            return path


def _behind(pending: int) -> str:
    """Say that the database is behind its revisions, and by how many."""
    if pending == 1:
        return "The database is behind its revisions: 1 revision is not applied."
    return f"The database is behind its revisions: {pending} revisions are not applied."
