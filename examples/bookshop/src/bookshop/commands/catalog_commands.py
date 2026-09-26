"""``catalog:*`` — a function command, a class command, arguments, options, questions."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, final

from xtr_console import (
    Argument,
    ConsoleStyle,
    ExitCode,
    Option,
    Range,
    Verbosity,
    as_command,
    escape,
)
from xtr_dependency_injection import Autowire, Injected

from bookshop.catalog import Book, BookCatalogInterface, Genre
from bookshop.pricing import PriceCalculator
from bookshop.reporting import ExportRegistry
from fulltext import SearchEngineInterface

__all__ = ["AddBookCommand", "list_books", "price_book"]


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
    rows = [
        {"isbn": b.isbn, "title": b.title, "author": b.author, "price": str(b.price)} for b in books
    ]
    if output != "table":
        # Machine-readable output: printed even under -q.
        io.text(await exporters.export(output, rows), verbosity=Verbosity.QUIET)
        return ExitCode.SUCCESS
    io.title("Catalog")
    io.table(["ISBN", "Title", "Author", "Price"], [list(row.values()) for row in rows])
    io.text(f"{len(rows)} of {len(catalog.all())} books", verbosity=Verbosity.VERBOSE)
    return ExitCode.SUCCESS


@as_command("catalog:price")
async def price_book(
    io: ConsoleStyle,
    isbn: str,
    quantity: Annotated[int, Argument(validator=Range(gte=1))] = 1,
    *,
    catalog: Injected[BookCatalogInterface],
    calculator: Injected[PriceCalculator],
) -> int:
    """Price a line through every pricing rule, in collection order.

    Args:
        io: Where the command writes.
        isbn: The book (an argument).
        quantity: How many copies (an optional argument).
        catalog: The catalog, from the container.
        calculator: The pricing rules, from the container.
    """
    book = catalog.find(isbn)
    if book is None:
        io.error(f"No book with ISBN {escape(isbn)}.")
        return ExitCode.FAILURE
    io.section(f"{escape(book.title)} x {quantity}")
    lines = calculator.price(book, quantity)
    io.table(["Step", calculator.currency], [[line.rule, str(line.amount)] for line in lines])
    return ExitCode.SUCCESS


@final
@as_command("catalog:add", description="Add a book to the catalog, and index it.")
class AddBookCommand:
    """A class command: built once by the container, with its constructor's services."""

    def __init__(self, catalog: BookCatalogInterface, engine: SearchEngineInterface) -> None:
        """Add to ``catalog``; index into ``engine``."""
        self._catalog = catalog
        self._engine = engine

    async def __call__(  # noqa: PLR0913 — the command line of the command.
        self,
        io: ConsoleStyle,
        isbn: str,
        title: str,
        price: Decimal,
        *,
        author: str = "",
        genre: Genre = Genre.FICTION,
        yes: Annotated[bool, Option(alias="-y")] = False,
    ) -> int:
        """Add a book.

        Args:
            io: Where the command writes.
            isbn: The ISBN.
            title: The title.
            price: The list price.
            author: Asked for when omitted.
            genre: Where it is shelved.
            yes: Do not ask for confirmation.
        """
        name = author or io.ask("Author?", "Anonymous")
        if self._catalog.find(isbn) is not None:
            io.caution(f"{escape(isbn)} is already in the catalog; it will be replaced.")
        if not yes and not io.confirm(f"Add {escape(title)!r} by {escape(name)}?", default=True):
            io.warning("Nothing added.")
            return ExitCode.FAILURE
        book = Book(isbn, title, name, price, genre)
        self._catalog.add(book)
        self._engine.index(book.isbn, book.describe())
        io.success(f"Added {escape(title)}.")
        return ExitCode.SUCCESS
