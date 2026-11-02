"""Handing the messages table over to a connection's migrations."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_orm import MappingDriverInterface

from .messages_table import messages_table

if TYPE_CHECKING:
    from sqlalchemy import MetaData

__all__ = ["MessagesTableDriver"]


@final
class MessagesTableDriver(MappingDriverInterface):
    """Adds the messages table to the definitions a connection's migrations compare with.

    With it loaded, the table is written by the next revision like any of the
    application's own, instead of created by the transport the first time it
    runs.
    """

    __slots__ = ("_table_name",)

    def __init__(self, table_name: str) -> None:
        """Map the messages table named ``table_name``."""
        self._table_name = table_name

    @override
    def load_metadata(self, metadata: MetaData, /) -> tuple[str, ...]:
        """Add the table to ``metadata`` unless it is there already; return what was added."""
        if self._table_name in metadata.tables:
            return ()
        _ = messages_table(metadata, self._table_name)
        return (self._table_name,)
