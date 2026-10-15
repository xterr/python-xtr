"""An extra say over whether a persistent token's value still counts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from .persistent_token import PersistentToken

__all__ = ["TokenVerifierInterface"]


@runtime_checkable
class TokenVerifierInterface(Protocol):
    """Decides whether a presented value still matches a persistent token.

    The plain check is equality, but a store that can afford it may accept a
    slightly outdated value — the rotation window — and this is where that
    policy plugs in. Comparisons must run in constant time
    (:func:`hmac.compare_digest`), so a presented value cannot be timed out
    of the real one.
    """

    async def verify_token(self, token: PersistentToken, token_value: str) -> bool:
        """Tell whether ``token_value`` is a value ``token`` accepts."""
        ...

    async def update_existing_token(
        self,
        token: PersistentToken,
        token_value: str,
        last_used: datetime,
    ) -> None:
        """Record ``token``'s new value and last use, without rotating it."""
        ...
