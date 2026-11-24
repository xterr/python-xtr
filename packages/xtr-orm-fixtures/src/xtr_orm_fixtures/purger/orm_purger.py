"""Emptying the tables of a set of table definitions, children first."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from sqlalchemy import MetaData, text

from .purge_mode import PurgeMode
from .purger_interface import PurgerInterface

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlalchemy import Table
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["OrmPurger"]

_MYSQL_DIALECTS = frozenset({"mysql", "mariadb"})


@final
class OrmPurger(PurgerInterface):
    """Empties every table of its definitions, a referencing table before the one it references.

    Only the tables the definitions hold are touched, so a table the
    application keeps outside them — or names in ``excluded``, by name or by
    schema-qualified name — keeps its rows.

    With :attr:`PurgeMode.TRUNCATE`, PostgreSQL empties every table in one
    ``TRUNCATE`` statement, without ``CASCADE``: a table left out that
    references one emptied makes the statement fail rather than be emptied
    too. MySQL and MariaDB truncate each table with foreign key checks off,
    turned back on whatever happens; they commit around every ``TRUNCATE``,
    so there the emptying cannot be rolled back. Any other database is
    emptied with ``DELETE``.
    """

    __slots__ = ("_excluded", "_metadata", "_mode")

    def __init__(
        self,
        metadata: MetaData | Sequence[MetaData],
        excluded: Iterable[str] = (),
        mode: PurgeMode = PurgeMode.DELETE,
    ) -> None:
        """Empty the tables of ``metadata``, but those of ``excluded``, as ``mode`` says."""
        self._metadata: tuple[MetaData, ...] = (
            (metadata,) if isinstance(metadata, MetaData) else tuple(metadata)
        )
        self._excluded = frozenset(excluded)
        self._mode = mode

    @property
    def excluded(self) -> frozenset[str]:
        """The tables left as they are, by name or schema-qualified name."""
        return self._excluded

    @property
    def mode(self) -> PurgeMode:
        """How the tables are emptied."""
        return self._mode

    def tables(self) -> list[Table]:
        """Return the tables emptied, in the order they are emptied."""
        return [
            table
            for metadata in self._metadata
            for table in reversed(metadata.sorted_tables)
            if table.name not in self._excluded and table.fullname not in self._excluded
        ]

    @override
    async def purge(self, session: AsyncSession) -> None:
        tables = self.tables()
        if not tables:
            return
        dialect = (await session.connection()).dialect
        if self._mode is PurgeMode.TRUNCATE and dialect.name == "postgresql":
            names = ", ".join(dialect.identifier_preparer.format_table(table) for table in tables)
            _ = await session.execute(text(f"TRUNCATE TABLE {names}"))
        elif self._mode is PurgeMode.TRUNCATE and dialect.name in _MYSQL_DIALECTS:
            _ = await session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            try:
                for table in tables:
                    name = dialect.identifier_preparer.format_table(table)
                    _ = await session.execute(text(f"TRUNCATE TABLE {name}"))
            finally:
                _ = await session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        else:
            for table in tables:
                _ = await session.execute(table.delete())
