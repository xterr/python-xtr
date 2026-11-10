"""``catalog:snapshot`` — read what the cache warmers wrote, without asking the catalog."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, cast

from xtr_console import ConsoleStyle, ExitCode, Verbosity, as_command, escape
from xtr_dependency_injection import Autowire

from bookshop.service.catalog_snapshot_warmer import CATALOG_SNAPSHOT
from bookshop.service.genre_index_warmer import GENRE_INDEX

__all__ = ["catalog_snapshot"]


@as_command("catalog:snapshot")
async def catalog_snapshot(
    io: ConsoleStyle,
    cache_dir: Annotated[str, Autowire(param="kernel.cache_dir")],
    build_dir: Annotated[str, Autowire(param="kernel.build_dir")],
) -> int:
    """Show the catalog snapshot the kernel warmed at boot, and the genre index if it exists.

    The snapshot is there on every start: the kernel writes it when the cache is cold. The
    genre index comes from an optional warmer, so it is there only after ``cache:warmup`` or
    ``cache:clear``; ``cache:clear --no-warmup`` removes both, and the next start writes the
    snapshot again.

    Args:
        io: Where the command writes.
        cache_dir: The ``kernel.cache_dir`` parameter, ``var/cache/<environment>``.
        build_dir: The ``kernel.build_dir`` parameter.
    """
    snapshot = Path(cache_dir) / CATALOG_SNAPSHOT
    index = Path(build_dir) / GENRE_INDEX
    io.title("Catalog snapshot")
    io.text(f"In {escape(cache_dir)}", verbosity=Verbosity.VERBOSE)
    io.table(
        ["Cache", "State"],
        [["snapshot", _describe(snapshot, "books")], ["genre index", _describe(index, "genres")]],
    )
    return ExitCode.SUCCESS if snapshot.is_file() else ExitCode.FAILURE


def _describe(file: Path, counted: str) -> str:
    """Say where ``file`` is, how many entries it holds and when it was written."""
    if not file.is_file():
        return f"{file.name} — missing"
    entries = len(cast("list[object] | dict[str, object]", json.loads(file.read_text())))
    written = datetime.fromtimestamp(file.stat().st_mtime, tz=UTC).strftime("%H:%M:%S")
    return f"{file.name} — {entries} {counted}, written {written} UTC"
