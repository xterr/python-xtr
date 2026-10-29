"""``catalog:list`` — a function command with an alias, an Enum, a ``Literal`` and a validator."""

from __future__ import annotations

from typing import Annotated, Literal

from xtr_console import ConsoleStyle, ExitCode, Option, Range, Verbosity, as_command
from xtr_dependency_injection import Autowire, Injected

from bookshop.service.book_catalog_interface import BookCatalogInterface
from bookshop.service.book_rows import book_rows
from bookshop.service.export_registry import ExportRegistry
from bookshop.service.genre import Genre

__all__ = ["list_books"]


@as_command("catalog:list", aliases="books")
async def list_books(  # noqa: PLR0913 — the command line, the style and three services.
    io: ConsoleStyle,
    catalog: Injected[BookCatalogInterface],
    exporters: Injected[ExportRegistry],
    page_size: Annotated[int, Autowire(param="shop.page_size")],
    *,
    genre: Genre | None = None,
    limit: Annotated[int | None, Option(alias="-l", validator=Range(gte=1))] = None,
    output: Literal["table", "csv", "json", "markdown"] = "table",
) -> int:
    """List the catalog.

    Args:
        io: Where the command writes.
        catalog: The (decorated) catalog, from the container.
        exporters: Exporters by format, from the container.
        page_size: The ``shop.page_size`` parameter — an ``%env(int:...)%`` placeholder.
        genre: Only books of this genre (an Enum option: ``--genre software``).
        limit: At most this many books; the page size when omitted.
        output: How to print them (a ``Literal`` option: anything else is refused).
    """
    books = [book for book in catalog.all() if genre is None or book.genre is genre]
    books = books[: limit or page_size]
    rows = book_rows(books)
    if output != "table":
        # Machine-readable output: printed even under -q.
        io.text(await exporters.export(output, rows), verbosity=Verbosity.QUIET)
        return ExitCode.SUCCESS
    io.title("Catalog")
    io.table(["ISBN", "Title", "Author", "Price"], [list(row.values()) for row in rows])
    io.text(f"{len(rows)} of {len(catalog.all())} books", verbosity=Verbosity.VERBOSE)
    return ExitCode.SUCCESS
