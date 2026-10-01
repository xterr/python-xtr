"""Async streams of vote results, for driving a decision strategy."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

    from xtr_security_core.authorization.voter import Access


async def stream(results: Iterable[Access]) -> AsyncIterator[Access]:
    """Yield each result in turn."""
    for result in results:
        yield result


async def counting_stream(
    results: Iterable[Access],
    pulled: list[Access],
) -> AsyncIterator[Access]:
    """Yield each result, recording in ``pulled`` the ones actually drawn."""
    for result in results:
        pulled.append(result)
        yield result
