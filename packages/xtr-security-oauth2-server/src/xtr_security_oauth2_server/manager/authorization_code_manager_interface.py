"""Where stored authorization codes are read, written and swept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_oauth2_server.model.authorization_code_interface import (
        AuthorizationCodeInterface,
    )

__all__ = ["AuthorizationCodeManagerInterface"]


@runtime_checkable
class AuthorizationCodeManagerInterface(Protocol):
    """Reads and writes the stored authorization codes, and sweeps the expired ones.

    A code lives for minutes and is redeemed once, so what is stored is only
    enough to refuse the second attempt. Sweeping matters more here than
    anywhere else for the same reason: a busy server writes one of these per
    authorization and never reads most of them again.
    """

    async def find(self, identifier: str) -> AuthorizationCodeInterface | None:
        """Return the code stored as ``identifier``, or ``None``."""
        ...

    async def save(self, auth_code: AuthorizationCodeInterface) -> None:
        """Store ``auth_code``, new or already known."""
        ...

    async def clear_expired(self) -> int:
        """Forget every code that has expired, and return how many went."""
        ...
