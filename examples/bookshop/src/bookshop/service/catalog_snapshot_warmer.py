"""A cache warmer the kernel runs when it boots with a cold cache.

It subclasses ``CacheWarmer``, so the kernel bundle tags it ``kernel.cache_warmer`` without
being told, and it is not optional: ``catalog:snapshot`` reads what it writes and has nothing
to show without it. The kernel runs it once — on the first start, after ``cache:clear``, or
after this module changes — and every later start skips it (``.warmed`` in the cache
directory records the build it ran for). ``cache:warmup`` runs it on demand.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, final

from typing_extensions import override
from xtr_dependency_injection import CacheWarmer, as_service

from bookshop.service.book_catalog_interface import BookCatalogInterface
from bookshop.service.book_rows import book_rows

__all__ = ["CATALOG_SNAPSHOT", "CatalogSnapshotWarmer"]

CATALOG_SNAPSHOT: Final = "catalog.json"
"""The file, in ``kernel.cache_dir``, holding every book as the catalog commands print it."""


@final
@as_service
class CatalogSnapshotWarmer(CacheWarmer):
    """Writes every book of the catalog to ``catalog.json`` in the cache directory."""

    def __init__(self, catalog: BookCatalogInterface) -> None:
        """Snapshot ``catalog`` — the decorated one, as everything else sees it."""
        self._catalog = catalog

    @override
    async def warm_up(self, cache_dir: Path, build_dir: Path | None = None) -> None:
        rows = book_rows(self._catalog.all())
        self._write_cache_file(cache_dir / CATALOG_SNAPSHOT, json.dumps(rows, indent=2))

    @override
    def is_optional(self) -> bool:
        return False
