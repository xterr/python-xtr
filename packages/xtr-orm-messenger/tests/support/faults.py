"""Making a connection's statement fail the way a database would, a set number of times."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_orm_messenger.transport import Connection

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import pytest
    from sqlalchemy.exc import DBAPIError


def failing(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    errors: list[DBAPIError],
) -> list[int]:
    """Make ``Connection.<method>`` raise each of ``errors`` in turn, then behave.

    Returns the list the number of calls is counted in, so a test can tell how
    many times the statement was tried.
    """
    original = cast("Callable[..., Awaitable[object]]", getattr(Connection, method))
    calls = [0]
    remaining = list(errors)

    async def flaky(self: Connection, *args: object) -> object:
        calls[0] += 1
        if remaining:
            raise remaining.pop(0)
        return await original(self, *args)

    monkeypatch.setattr(Connection, method, flaky)
    return calls
