"""Two decorators stacked on one service, ordered by priority.

The highest priority wraps the original, each next one wraps the previous result:

    AuditedBookCatalog (priority 0)
      └── CachingBookCatalog (priority 10)
            └── InMemoryBookCatalog (from book_catalog)

Everything asking for ``BookCatalogInterface`` gets the outermost one. Each decorator
receives what it wraps through its single ``Annotated[T, AutowireDecorated()]`` parameter,
and ``on_invalid`` is left at ``OnInvalid.EXCEPTION``: the catalog must exist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, final

from typing_extensions import override
from xtr_dependency_injection import AutowireDecorated, Target, as_decorator
from xtr_logging_contracts import LoggerInterface
from xtr_service_contracts import ResetInterface

from .book_catalog_interface import BookCatalogInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .book import Book

__all__ = ["AuditedBookCatalog", "CachingBookCatalog"]


@final
@as_decorator(BookCatalogInterface, priority=10)
class CachingBookCatalog(BookCatalogInterface, ResetInterface):
    """Memoises lookups.

    It inherits ``ResetInterface`` explicitly, so the kernel bundle's nominal
    autoconfiguration tags it ``kernel.reset`` with ``method="reset"``: the worker, the web
    server and ``cache:clear`` call ``ServicesResetter.reset()`` and the cache empties.
    """

    __slots__ = ("_hits", "_inner", "_lookups")

    def __init__(self, inner: Annotated[BookCatalogInterface, AutowireDecorated()]) -> None:
        """Wrap ``inner``."""
        self._inner = inner
        self._lookups: dict[str, Book | None] = {}
        self._hits = 0

    @property
    def hits(self) -> int:
        """How many lookups the cache answered since the last reset."""
        return self._hits

    @override
    def all(self) -> Sequence[Book]:
        return self._inner.all()

    @override
    def find(self, isbn: str, /) -> Book | None:
        if isbn in self._lookups:
            self._hits += 1
            return self._lookups[isbn]
        found = self._inner.find(isbn)
        self._lookups[isbn] = found
        return found

    @override
    def add(self, book: Book, /) -> None:
        _ = self._lookups.pop(book.isbn, None)
        self._inner.add(book)

    @override
    def reset(self) -> None:
        self._lookups.clear()
        self._hits = 0


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
