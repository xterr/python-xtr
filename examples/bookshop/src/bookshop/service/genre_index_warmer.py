"""An optional cache warmer: only ``cache:warmup`` and ``cache:clear`` run it.

``catalog:snapshot`` can work out the genres from the catalog itself; the index only spares it
the work. So the warmer is optional, and the kernel skips it at boot. It writes to the build
directory — where what is only ever read goes — falling back to the cache directory when the
caller gives none.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, final

from typing_extensions import override
from xtr_dependency_injection import CacheWarmer, as_service

from bookshop.service.book_catalog_interface import BookCatalogInterface

__all__ = ["GENRE_INDEX", "GenreIndexWarmer"]

GENRE_INDEX: Final = "genres.json"
"""The file, in ``kernel.build_dir``, mapping each genre to the ISBNs shelved under it."""


@final
@as_service
class GenreIndexWarmer(CacheWarmer):
    """Writes ``genres.json``: every genre, and the ISBNs of its books."""

    def __init__(self, catalog: BookCatalogInterface) -> None:
        """Index ``catalog``."""
        self._catalog = catalog

    @override
    async def warm_up(self, cache_dir: Path, build_dir: Path | None = None) -> None:
        index: dict[str, list[str]] = {}
        for book in self._catalog.all():
            index.setdefault(book.genre.value, []).append(book.isbn)
        target = build_dir if build_dir is not None else cache_dir
        self._write_cache_file(target / GENRE_INDEX, json.dumps(index, indent=2))

    @override
    def is_optional(self) -> bool:
        return True
