"""Refresh tokens kept in this process, revoked by exactly one caller."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_clock import (
    ClockInterface,  # noqa: TC002 -- container hydrates this constructor at runtime
)

from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (
    RefreshTokenManagerInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server.model.refresh_token_interface import RefreshTokenInterface

__all__ = ["RefreshTokenManager"]


@final
class RefreshTokenManager(RefreshTokenManagerInterface):
    """Holds the refresh tokens in a mapping, for one process.

    For tests and single-process demonstrations. :meth:`revoke` decides and
    writes without awaiting anything in between, so within this process the
    two halves cannot be interleaved and exactly one of two concurrent
    refreshes is told it revoked the token — the same guarantee a conditional
    update gives against a database, and the reason that guarantee is worth
    stating even here.

    Across processes it gives nothing, because there is nothing shared to
    race over.
    """

    def __init__(self, clock: ClockInterface) -> None:
        """Read expiry against ``clock``."""
        self._clock = clock
        self._refresh_tokens: dict[str, RefreshTokenInterface] = {}

    @override
    def __repr__(self) -> str:
        """Name the type and how many tokens are held, never which."""
        return f"{type(self).__name__}(held={len(self._refresh_tokens)})"

    @override
    async def find(self, identifier: str) -> RefreshTokenInterface | None:
        """Return the token stored as ``identifier``, or ``None``."""
        return self._refresh_tokens.get(identifier)

    @override
    async def save(self, refresh_token: RefreshTokenInterface) -> None:
        """Store ``refresh_token``, new or already known."""
        self._refresh_tokens[refresh_token.get_identifier()] = refresh_token

    @override
    async def revoke(self, identifier: str) -> bool:
        """Withdraw the token stored as ``identifier``, and say whether this call did."""
        token = self._refresh_tokens.get(identifier)
        if token is None or token.is_revoked():
            return False

        _ = token.revoke()

        return True

    @override
    async def clear_expired(self) -> int:
        """Forget every token that has expired, and return how many went."""
        now = self._clock.now()
        kept = {
            identifier: token
            for identifier, token in self._refresh_tokens.items()
            if token.get_expiry() >= now
        }
        cleared = len(self._refresh_tokens) - len(kept)
        self._refresh_tokens = kept

        return cleared
