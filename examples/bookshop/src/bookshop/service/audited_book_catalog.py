"""The outer of the two decorators on the catalog — see ``caching_book_catalog`` for the stack."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, final

from typing_extensions import override
from xtr_dependency_injection import AutowireDecorated, Target, as_decorator
from xtr_logging_contracts import LoggerInterface

from bookshop.service.book_catalog_interface import BookCatalogInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from bookshop.service.book import Book

__all__ = ["AuditedBookCatalog"]


@final
@as_decorator(BookCatalogInterface)
class AuditedBookCatalog(BookCatalogInterface):
    """Logs every change to the ``security`` channel — decorators take dependencies too."""

    __slots__ = ("_audit", "_inner")

    def __init__(
        self,
        inner: Annotated[BookCatalogInterface, AutowireDecorated()],
        audit: Annotated[LoggerInterface, Target("security")],
    ) -> None:
        """Wrap ``inner``; write to ``audit``."""
        self._inner = inner
        self._audit = audit

    @override
    def all(self) -> Sequence[Book]:
        return self._inner.all()

    @override
    def find(self, isbn: str, /) -> Book | None:
        return self._inner.find(isbn)

    @override
    def add(self, book: Book, /) -> None:
        self._audit.warning("catalog changed: {isbn}", {"isbn": book.isbn, "title": book.title})
        self._inner.add(book)
