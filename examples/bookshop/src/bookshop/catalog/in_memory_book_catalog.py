"""The catalog implementation, and the factory that registers it under its interface."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Final, final

from typing_extensions import override
from xtr_dependency_injection import Target, as_service
from xtr_logging_contracts import LoggerInterface

from .book import Book, Genre
from .book_catalog_interface import BookCatalogInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["InMemoryBookCatalog", "book_catalog"]

_SEED: Final = (
    Book(
        "978-0135957059",
        "The Pragmatic Programmer",
        "Hunt, Thomas",
        Decimal("42.00"),
        Genre.SOFTWARE,
    ),
    Book("978-0201633610", "Design Patterns", "Gamma et al.", Decimal("54.50"), Genre.SOFTWARE),
    Book("978-0141439518", "Pride and Prejudice", "Austen", Decimal("9.99"), Genre.FICTION),
    Book("978-0140449136", "Crime and Punishment", "Dostoevsky", Decimal("12.40"), Genre.FICTION),
    Book("978-0393317558", "Guns, Germs, and Steel", "Diamond", Decimal("19.90"), Genre.HISTORY),
)


@final
class InMemoryBookCatalog(BookCatalogInterface):
    """Books in a dict, seeded with a handful of titles.

    Not decorated itself: :func:`book_catalog` builds it, so the key the container knows is
    the interface, and the decorators in ``catalog_decorators`` wrap that key.
    """

    __slots__ = ("_books", "_logger")

    def __init__(self, logger: LoggerInterface) -> None:
        """Start with the seed titles; log changes through ``logger``."""
        self._books: dict[str, Book] = {book.isbn: book for book in _SEED}
        self._logger = logger

    @override
    def all(self) -> Sequence[Book]:
        return tuple(self._books.values())

    @override
    def find(self, isbn: str, /) -> Book | None:
        return self._books.get(isbn)

    @override
    def add(self, book: Book, /) -> None:
        self._books[book.isbn] = book
        self._logger.notice("catalog now holds {title}", {"title": book.title, "isbn": book.isbn})


@as_service
def book_catalog(
    logger: Annotated[LoggerInterface, Target("catalog")],
) -> BookCatalogInterface:
    """Provide the catalog under :class:`BookCatalogInterface` — ``@as_service`` on a factory.

    A factory is registered under its evaluated *return* type, so this is the definition
    ``(BookCatalogInterface, None)``. ``Target("catalog")`` asks for the logger qualified by
    the ``catalog`` channel rather than the default channel's.
    """
    return InMemoryBookCatalog(logger)
