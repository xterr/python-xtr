"""What handles the schedule's own message."""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Injected, Target
from xtr_logging_contracts import LoggerInterface
from xtr_messenger import as_message_handler

from bookshop.message.restock_check import RestockCheck
from bookshop.service.book_catalog_interface import BookCatalogInterface

__all__ = ["check_restock"]


@as_message_handler(RestockCheck)
async def check_restock(
    message: RestockCheck,
    catalog: Injected[BookCatalogInterface],
    logger: Annotated[LoggerInterface, Target("scheduler")],
) -> int:
    """Look at every title; return how many — the run's result, which ``PostRunEvent`` carries."""
    titles = len(catalog.all())
    logger.info("{check}: {titles} titles looked at", {"check": str(message), "titles": titles})
    return titles
