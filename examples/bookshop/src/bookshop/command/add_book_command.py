"""``catalog:add`` — a class command, options and questions."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, final

from xtr_console import ConsoleStyle, ExitCode, Option, as_command, escape

from bookshop.service.book import Book
from bookshop.service.book_catalog_interface import BookCatalogInterface
from bookshop.service.genre import Genre
from fulltext import SearchEngineInterface

__all__ = ["AddBookCommand"]


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
