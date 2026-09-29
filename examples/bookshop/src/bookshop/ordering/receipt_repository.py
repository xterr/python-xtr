"""Receipts, through an advanced-alchemy repository on the unit's session."""

from __future__ import annotations

from typing import final

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy.ext.asyncio import AsyncSession
from xtr_dependency_injection import as_service

from .receipt import Receipt

__all__ = ["ReceiptRepository", "receipt_repository"]


@final
class ReceiptRepository(SQLAlchemyAsyncRepository[Receipt]):
    """Receipts, one row per transport a ``SendReceipt`` came through."""

    model_type = Receipt


@as_service(lifetime="scoped")
def receipt_repository(session: AsyncSession) -> ReceiptRepository:
    """One repository per scope, on that scope's session — see ``order_repository``."""
    return ReceiptRepository(session=session)
