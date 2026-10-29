"""A task class, called through ``method=`` — see ``bookshop.scheduler``."""

from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Target
from xtr_logging_contracts import LoggerInterface
from xtr_scheduler.decorator import as_periodic_task

from bookshop.service.book_catalog_interface import BookCatalogInterface

__all__ = ["CatalogReport"]


@final
@as_periodic_task("10 minutes", jitter=30, method="build")
class CatalogReport:
    """A task class: built by the container, called through ``method``."""

    def __init__(
        self,
        catalog: BookCatalogInterface,
        logger: Annotated[LoggerInterface, Target("scheduler")],
    ) -> None:
        """Report on ``catalog``."""
        self._catalog = catalog
        self._logger = logger

    def build(self) -> int:
        """Count the catalog — the count is the run's result."""
        size = len(self._catalog.all())
        self._logger.info("catalog report: {size} titles", {"size": size})
        return size
