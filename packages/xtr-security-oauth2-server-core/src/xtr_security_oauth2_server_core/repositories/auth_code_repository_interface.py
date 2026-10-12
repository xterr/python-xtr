"""Where authorization codes are minted, stored and revoked."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .repository_interface import RepositoryInterface

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.auth_code_entity_interface import (
        AuthCodeEntityInterface,
    )

__all__ = ["AuthCodeRepositoryInterface"]


@runtime_checkable
class AuthCodeRepositoryInterface(RepositoryInterface, Protocol):
    """Mints the authorization-code entity, stores it, and answers for its life.

    A code is single use: the token endpoint revokes the code it just redeemed,
    and a second attempt with the same code finds it revoked. That is what the
    revocation pair is for here — not an administrator withdrawing something,
    but the ordinary end of a code's life, one exchange after it was issued.
    """

    async def get_new_auth_code(self) -> AuthCodeEntityInterface:
        """Return a new, unstored authorization code."""
        ...

    async def persist_new_auth_code(self, auth_code_entity: AuthCodeEntityInterface) -> None:
        """Store ``auth_code_entity``.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When a code of that
                identifier is already stored. The grant answers by minting
                another identifier and trying again.
        """
        ...

    async def revoke_auth_code(self, code_id: str) -> None:
        """Stop accepting the authorization code named ``code_id``.

        Revoking one that is unknown, or already revoked, is not an error:
        what the caller asked for is already true.
        """
        ...

    async def is_auth_code_revoked(self, code_id: str) -> bool:
        """Tell whether the authorization code named ``code_id`` was revoked."""
        ...
