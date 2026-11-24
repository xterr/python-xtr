"""The table definitions of each connection fixtures may load into."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import MetaData

from .exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["TableDefinitions"]


@final
class TableDefinitions:
    """The table definitions of each connection, by connection name.

    They say which tables a purger empties: those the application maps, and
    no other table the database holds. Built by hand without a container; a
    container builds it from the connections it configures.
    """

    __slots__ = ("_definitions",)

    def __init__(self, definitions: Mapping[str, MetaData | Sequence[MetaData]]) -> None:
        """Keep ``definitions``, by connection name."""
        self._definitions = dict(definitions)

    def for_connection(self, name: str) -> MetaData | Sequence[MetaData]:
        """Return the table definitions of the connection ``name``.

        Raises:
            InvalidArgumentError: If no connection is named ``name``, or it
                keeps no table definitions.
        """
        found = self._definitions.get(name)
        if found is None:
            known = ", ".join(self._definitions) or "none"
            raise InvalidArgumentError(
                f'No connection is named "{name}"; the connections are: {known}'
            )
        if not isinstance(found, MetaData) and not found:
            raise InvalidArgumentError(f'The "{name}" connection keeps no table definitions')
        return found
