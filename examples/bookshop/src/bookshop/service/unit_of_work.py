"""A scoped service from a generator factory, with cleanup when its scope ends."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, final
from uuid import uuid4

from xtr_dependency_injection import Target, as_service
from xtr_logging_contracts import EXCEPTION_KEY, LoggerInterface

__all__ = ["UnitOfWork", "unit_of_work"]


@final
class UnitOfWork:
    """What one command run or one web request changed, committed at the end or rolled back."""

    __slots__ = ("changes", "committed", "id")

    def __init__(self) -> None:
        """Open a unit of work with a fresh id."""
        self.id = uuid4().hex[:8]
        self.changes: list[str] = []
        self.committed = False

    def record(self, change: str) -> None:
        """Remember ``change``."""
        self.changes.append(change)


@as_service(lifetime="scoped")
async def unit_of_work(
    logger: Annotated[LoggerInterface, Target("orders")],
) -> AsyncIterator[UnitOfWork]:
    """Open a unit of work for the scope, commit it when the scope ends cleanly.

    ``lifetime="scoped"``: one per scope — every parameter asking for it within one command
    run or one request gets the same instance. A generator factory's code after ``yield``
    runs as the scope closes; when the scope ends with an error, the error is thrown into
    the generator at the ``yield``, so the ``except`` branch is the rollback.
    """
    work = UnitOfWork()
    logger.debug("unit of work {id} opened", {"id": work.id})
    try:
        yield work
    except Exception as error:
        logger.error("unit of work {id} rolled back", {"id": work.id, EXCEPTION_KEY: error})
        raise
    work.committed = True
    logger.info(
        "unit of work {id} committed {count} changes", {"id": work.id, "count": len(work.changes)}
    )
