"""The queries one unit of work ran — state to forget between requests and messages."""

from __future__ import annotations

from typing import final

__all__ = ["QueryLog"]


@final
class QueryLog:
    """Remembers the queries run since it was last cleared.

    It does not inherit ``ResetInterface``: its reset method is called ``clear``, so the bundle
    opts it in explicitly with ``add_tag("kernel.reset", method="clear")`` — and the kernel's
    ``ResettableServicePass`` checks at build time that the method exists.
    """

    __slots__ = ("_queries",)

    def __init__(self) -> None:
        """Start empty."""
        self._queries: list[str] = []

    def record(self, query: str) -> None:
        """Remember ``query``."""
        self._queries.append(query)

    def queries(self) -> tuple[str, ...]:
        """Every query since the last :meth:`clear`."""
        return tuple(self._queries)

    def clear(self) -> None:
        """Forget every query."""
        self._queries.clear()
