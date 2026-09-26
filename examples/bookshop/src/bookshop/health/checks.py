"""The startup checks, placed with ``priority``, ``before`` and ``after``.

Each check is its own key — ``(CatalogCheck, None)`` and so on — so ``before``/``after``
can name the others by type. The kernel's emission order, which ``debug:container`` prints
and :func:`bookshop.lifecycle.run_startup_checks` follows, becomes:

1. ``ConfigurationCheck`` — priority 10;
2. ``CatalogCheck`` — no priority, ``before=[SearchIndexCheck]``;
3. ``SearchIndexCheck`` — priority 0;
4. ``MessengerCheck`` — no priority, ``after=[SearchIndexCheck]``.

They are declared in another order on purpose: the order comes from the constraints, not
from the source. A contradiction (``before`` a lower priority) is a ``ServiceOrderError``.
"""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import KernelInterface, as_tagged_item
from xtr_messenger import MessageBusInterface
from xtr_service_contracts import ContainerInterface

from bookshop.catalog import BookCatalogInterface
from fulltext import SearchEngineInterface

from .startup_check import StartupCheck

__all__ = ["CatalogCheck", "ConfigurationCheck", "MessengerCheck", "SearchIndexCheck"]


@final
@as_tagged_item(priority=0)
class SearchIndexCheck(StartupCheck):
    """Indexes every book, so the first search already finds something."""

    def __init__(self, catalog: BookCatalogInterface, engine: SearchEngineInterface) -> None:
        """Index ``catalog`` into ``engine``."""
        self._catalog = catalog
        self._engine = engine

    @override
    async def run(self) -> str:
        books = self._catalog.all()
        for book in books:
            self._engine.index(book.isbn, book.describe())
        return f"indexed {len(books)} books"


@final
@as_tagged_item(after=[SearchIndexCheck])
class MessengerCheck(StartupCheck):
    """The bus exists — asked through ``ContainerInterface.has``, without building it."""

    def __init__(self, container: ContainerInterface) -> None:
        """Ask ``container``."""
        self._container = container

    @override
    async def run(self) -> str:
        if not self._container.has(MessageBusInterface):
            raise RuntimeError("the messenger bundle is not active")
        return "message bus registered"


@final
@as_tagged_item(before=[SearchIndexCheck])
class CatalogCheck(StartupCheck):
    """The catalog is not empty — before anything indexes it."""

    def __init__(self, catalog: BookCatalogInterface) -> None:
        """Check ``catalog``."""
        self._catalog = catalog

    @override
    async def run(self) -> str:
        count = len(self._catalog.all())
        if count == 0:
            raise RuntimeError("the catalog is empty")
        return f"{count} books in the catalog"


@final
@as_tagged_item(priority=10)
class ConfigurationCheck(StartupCheck):
    """The kernel runs in an environment the application knows."""

    def __init__(self, kernel: KernelInterface) -> None:
        """Check ``kernel``."""
        self._kernel = kernel

    @override
    async def run(self) -> str:
        return f"{self._kernel.name} in {self._kernel.environment}, debug={self._kernel.debug}"
