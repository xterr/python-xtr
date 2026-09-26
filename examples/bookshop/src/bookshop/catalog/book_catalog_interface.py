"""What the rest of the application asks for when it needs books."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .book import Book

__all__ = ["BookCatalogInterface"]


@runtime_checkable
class BookCatalogInterface(Protocol):
    """The books the shop sells.

    Services depend on this interface, never on an implementation: the container decides
    which implementation — and which decorators around it — they receive.
    """

    def all(self) -> Sequence[Book]:
        """Every book, in catalog order."""
        ...

    def find(self, isbn: str, /) -> Book | None:
        """The book with ``isbn``, or ``None``."""
        ...

    def add(self, book: Book, /) -> None:
        """Add or replace ``book``."""
        ...
