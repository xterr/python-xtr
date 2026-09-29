"""Orders, read and written through an advanced-alchemy repository on the unit's session."""

from __future__ import annotations

from typing import final

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy.ext.asyncio import AsyncSession
from xtr_dependency_injection import as_service

from .order import Order

__all__ = ["OrderRepository", "order_repository"]


@final
class OrderRepository(SQLAlchemyAsyncRepository[Order]):
    """Every repository method — ``add``, ``get_one_or_none``, ``list``, ``count`` — on orders."""

    model_type = Order


@as_service(lifetime="scoped")
def order_repository(session: AsyncSession) -> OrderRepository:
    """One repository per scope, on that scope's session.

    Scoped like the session it wraps: every handler of one message — a unit of work — gets
    the same repository and the same session, so ``orm_transaction`` commits what they all
    did at once. A command run and a web request are scopes of their own.
    """
    return OrderRepository(session=session)
