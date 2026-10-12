"""Where refresh tokens are minted, stored and revoked."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .repository_interface import RepositoryInterface

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )

__all__ = ["RefreshTokenRepositoryInterface"]


@runtime_checkable
class RefreshTokenRepositoryInterface(RepositoryInterface, Protocol):
    """Mints the refresh-token entity, stores it, and answers for its life.

    :meth:`revoke_refresh_token` reports whether *this* call is the one that
    revoked the token, which is what closes the window two refreshes of the
    same token would otherwise race through: both can read it as valid, and
    only one can be told it revoked it. The refresh grant treats ``False`` as
    an invalid refresh token, so the loser of the race gets no token and the
    pair of them cannot both succeed.

    An implementation therefore revokes conditionally — one statement that
    revokes only a token not already revoked, and reports whether it changed
    anything — rather than reading, deciding, and writing.
    """

    async def get_new_refresh_token(self) -> RefreshTokenEntityInterface | None:
        """Return a new, unstored refresh token, or ``None`` to issue none.

        Answering ``None`` is how a deployment opts out of refresh tokens
        without turning the grant off: the token response then simply carries
        no refresh token.
        """
        ...

    async def persist_new_refresh_token(
        self,
        refresh_token_entity: RefreshTokenEntityInterface,
    ) -> None:
        """Store ``refresh_token_entity``.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When a token of
                that identifier is already stored. The grant answers by
                minting another identifier and trying again.
        """
        ...

    async def revoke_refresh_token(self, token_id: str) -> bool:
        """Stop accepting the refresh token named ``token_id``.

        Returns:
            Whether this call is what revoked it: ``True`` when the token was
            valid and is now revoked, ``False`` when it was already revoked or
            is unknown.
        """
        ...

    async def is_refresh_token_revoked(self, token_id: str) -> bool:
        """Tell whether the refresh token named ``token_id`` was revoked."""
        ...
