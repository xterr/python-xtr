"""What builds the purger of a run."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlalchemy import MetaData

    from .purger_interface import PurgerInterface

__all__ = ["PurgerFactoryInterface"]


@runtime_checkable
class PurgerFactoryInterface(Protocol):
    """Builds the purger a run empties its connection with.

    A run picks a factory by name, so an application can empty its database
    its own way — keep a table of reference data, reset sequences — without
    replacing the command.
    """

    def create_for_connection(
        self,
        connection: str,
        metadata: MetaData | Sequence[MetaData],
        *,
        excluded: Iterable[str] = (),
        purge_with_truncate: bool = False,
    ) -> PurgerInterface:
        """Build the purger of the connection named ``connection``.

        Args:
            connection: The name of the connection the run loads into.
            metadata: The table definitions of that connection.
            excluded: Tables to leave as they are, by name or schema-qualified name.
            purge_with_truncate: Empty with ``TRUNCATE`` rather than ``DELETE``.
        """
        ...
