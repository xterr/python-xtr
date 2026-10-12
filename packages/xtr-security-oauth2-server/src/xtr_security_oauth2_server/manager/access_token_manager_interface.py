"""Where stored access tokens are read, written and swept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_oauth2_server.model.access_token_interface import AccessTokenInterface

__all__ = ["AccessTokenManagerInterface"]


@runtime_checkable
class AccessTokenManagerInterface(Protocol):
    """Reads and writes the stored access tokens, and sweeps the expired ones.

    The storage half of access tokens: the protocol never comes here, the
    access-token repository bridge does. That is the seam a deployment
    replaces to keep its tokens somewhere else, and the reason there is no
    "find by client" or "find by user" here — nothing in the protocol asks
    for either.

    Every method is awaitable, because every one of them may reach a database.
    """

    async def find(self, identifier: str) -> AccessTokenInterface | None:
        """Return the token stored as ``identifier``, or ``None``."""
        ...

    async def save(self, access_token: AccessTokenInterface) -> None:
        """Store ``access_token``, new or already known."""
        ...

    async def clear_expired(self) -> int:
        """Forget every token that has expired, and return how many went."""
        ...
