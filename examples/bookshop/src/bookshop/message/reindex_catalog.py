"""Reindexing the catalog: a pydantic message declaring its own transport."""

from __future__ import annotations

from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field
from xtr_messenger import as_message

__all__ = ["ReindexCatalog"]


@as_message(name="bookshop.catalog.reindex.v1", transport="jobs")
class ReindexCatalog(BaseModel):
    """Rebuild the search index — a pydantic model, validated by its own rules.

    Not in the routing table: it goes to the transport it declares, ``jobs``.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    reason: Annotated[str, Field(min_length=3)]
    isbns: tuple[str, ...] = ()
