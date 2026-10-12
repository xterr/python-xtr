"""The table a model was mapped to, which is where its columns are named."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sqlalchemy.orm import class_mapper

if TYPE_CHECKING:
    from sqlalchemy import Table

__all__ = ["mapped_table"]


def mapped_table(model: type[object], /) -> Table:
    """Return the table ``model`` is mapped to.

    The storage contracts of this package are written in models, so a manager
    names a model and the mapping finds the rows. A *condition* — swept once
    it expires, revoked only if it is not revoked yet, issued to this client —
    has to name a column instead, and the mapping is the only thing that
    knows which column an attribute became.

    Raises:
        UnmappedClassError: When ``model`` has not been mapped, which is what
            a deployment that turned this credential off asks for.
    """
    return cast("Table", class_mapper(model).local_table)
