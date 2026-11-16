"""The store behind persistent remember-me tokens."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from .persistent_token import PersistentToken

__all__ = ["TokenProviderInterface"]


@runtime_checkable
class TokenProviderInterface(Protocol):
    """Keeps the persistent remember-me token of every series.

    A database backs this in an application, which is why every method is
    awaitable: the store is reached over I/O, and the remember-me flow that
    calls it runs async.
    """

    async def load_token_by_series(self, series: str) -> PersistentToken:
        """Load the current token of ``series``.

        Raises an error when no token exists for the series. Which error is
        the provider's own, so its caller can tell a series that no longer
        exists apart from a store that failed.
        """
        ...

    async def delete_token_by_series(self, series: str) -> None:
        """Delete every token of ``series``."""
        ...

    async def update_token(
        self,
        series: str,
        expected_value: str,
        token_value: str,
        last_used: datetime,
    ) -> bool:
        """Rotate ``series``'s token to ``token_value`` if it still holds ``expected_value``.

        The check and the write are one step — a conditional ``UPDATE`` in a
        database — so of two requests rotating the same value at once only
        one wins; the other is told so and stores nothing.

        Returns:
            ``True`` when the value was rotated and its last use recorded;
            ``False`` when the stored value was no longer ``expected_value``.

        Raises an error when no token exists for the series, as
        :meth:`load_token_by_series` does.
        """
        ...

    async def create_new_token(self, token: PersistentToken) -> None:
        """Store ``token`` as a first entry of a new series."""
        ...
