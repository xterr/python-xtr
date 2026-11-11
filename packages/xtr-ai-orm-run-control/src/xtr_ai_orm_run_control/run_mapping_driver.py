"""Adding the run table to a connection's definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_orm import MappingDriverInterface

from .run_table import DEFAULT_TABLE_PREFIX, run_table

if TYPE_CHECKING:
    from sqlalchemy import MetaData

__all__ = ["RunMappingDriver"]


@final
class RunMappingDriver(MappingDriverInterface):
    """Adds ``{prefix}run`` to a connection's definitions.

    Register it through xtr-orm's ``OrmMappingsPass`` so the connection's
    migrations know the table; run control defines its own copy and needs
    nothing from here.
    """

    __slots__ = ("_table_prefix",)

    def __init__(self, table_prefix: str = DEFAULT_TABLE_PREFIX) -> None:
        """Add a table whose name starts with ``table_prefix``."""
        self._table_prefix = table_prefix

    @override
    def load_metadata(self, metadata: MetaData, /) -> tuple[str, ...]:
        """Add the table when ``metadata`` lacks it; return its name, ``()`` the second time."""
        known = set(metadata.tables)
        _ = run_table(metadata, self._table_prefix)
        return tuple(name for name in metadata.tables if name not in known)
