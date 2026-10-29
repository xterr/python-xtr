"""``catalog:export`` — a function command writing to a named storage."""

from __future__ import annotations

from typing import Annotated, Literal

from xtr_console import ConsoleStyle, ExitCode, as_command
from xtr_dependency_injection import Injected, Target
from xtr_storage import StorageOperatorInterface

from bookshop.service.book_catalog_interface import BookCatalogInterface
from bookshop.service.book_rows import book_rows
from bookshop.service.export_registry import ExportRegistry

__all__ = ["export_books"]


@as_command("catalog:export")
async def export_books(
    io: ConsoleStyle,
    catalog: Injected[BookCatalogInterface],
    exporters: Injected[ExportRegistry],
    reports: Annotated[StorageOperatorInterface, Target("reports")],
    *,
    output: Literal["csv", "json", "markdown"] = "csv",
) -> int:
    """Render the catalogue and keep the file in the ``reports`` storage.

    ``reports`` is the storage named in ``config/packages/storage.py``: local files rooted at the
    ``catalog`` prefix, so the export lands in ``var/storage/catalog/`` — in tests, in memory.
    Injection is qualified by the storage's name, the way a named cache pool is.

    Args:
        io: Where the command writes.
        catalog: The catalog, from the container.
        exporters: Exporters by format, from the container.
        reports: The ``reports`` storage, qualified.
        output: Which format to render.
    """
    location = f"catalog.{output}"
    await reports.write(
        location, (await exporters.export(output, book_rows(catalog.all()))).encode()
    )
    io.success(f"Stored {await reports.file_size(location)} bytes at reports://{location}.")
    return ExitCode.SUCCESS
