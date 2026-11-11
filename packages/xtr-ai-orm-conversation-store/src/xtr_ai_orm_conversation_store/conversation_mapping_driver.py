"""Adding the conversation tables to a connection's definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_orm import MappingDriverInterface

from .conversation_tables import DEFAULT_TABLE_PREFIX, ConversationTables

if TYPE_CHECKING:
    from sqlalchemy import MetaData

__all__ = ["ConversationMappingDriver"]


@final
class ConversationMappingDriver(MappingDriverInterface):
    """Adds the two conversation tables to a connection's definitions.

    Register it through xtr-orm's ``OrmMappingsPass`` so the connection's
    migrations know the tables; the store itself defines its own copy and needs
    nothing from here.
    """

    __slots__ = ("_table_prefix",)

    def __init__(self, table_prefix: str = DEFAULT_TABLE_PREFIX) -> None:
        """Add tables whose names start with ``table_prefix``."""
        self._table_prefix = table_prefix

    @override
    def load_metadata(self, metadata: MetaData, /) -> tuple[str, ...]:
        """Add the tables ``metadata`` lacks; return the names added, ``()`` the second time."""
        known = set(metadata.tables)
        _ = ConversationTables.define(metadata, self._table_prefix)
        return tuple(name for name in metadata.tables if name not in known)
