"""Where stored refresh tokens are read, written, revoked and swept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_oauth2_server.model.refresh_token_interface import RefreshTokenInterface

__all__ = ["RefreshTokenManagerInterface"]


@runtime_checkable
class RefreshTokenManagerInterface(Protocol):
    """Reads and writes the stored refresh tokens, and revokes one atomically.

    The only manager with a revoke of its own, and the reason is a race. Two
    refreshes of the same token can both read it as valid before either writes
    the revocation, and both would then be handed a new access token from one
    refresh token. :meth:`revoke` closes that window by deciding and writing
    in one step and reporting which caller won.

    An implementation must therefore revoke conditionally — one statement that
    revokes only a token not already revoked, and reports whether it changed
    anything — rather than finding a token, checking it, and saving it back.
    """

    async def find(self, identifier: str) -> RefreshTokenInterface | None:
        """Return the token stored as ``identifier``, or ``None``."""
        ...

    async def save(self, refresh_token: RefreshTokenInterface) -> None:
        """Store ``refresh_token``, new or already known."""
        ...

    async def revoke(self, identifier: str) -> bool:
        """Withdraw the token stored as ``identifier``, in one step.

        Returns:
            Whether this call is what withdrew it: ``True`` when the token was
            valid and is now revoked, ``False`` when it was already revoked or
            was never stored.
        """
        ...

    async def clear_expired(self) -> int:
        """Forget every token that has expired, and return how many went."""
        ...
