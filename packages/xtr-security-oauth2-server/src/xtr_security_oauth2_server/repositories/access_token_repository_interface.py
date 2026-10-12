"""Where access tokens are minted, stored and revoked."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .repository_interface import RepositoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface

__all__ = ["AccessTokenRepositoryInterface"]


@runtime_checkable
class AccessTokenRepositoryInterface(RepositoryInterface, Protocol):
    """Mints the access-token entity, stores it, and answers for its life.

    The grants never build a token themselves: they ask here, so an
    application's own entity — its mapped class, with its own columns — is
    what gets issued, and the grant only fills in the identifier and the
    expiry.

    A deployment that does not store its access tokens still implements this:
    storing becomes a no-op and nothing is ever reported revoked, which is the
    trade a self-describing token makes — no round trip to check it, and no
    way to withdraw it before it expires.
    """

    async def get_new_token(
        self,
        client_entity: ClientEntityInterface,
        scopes: Sequence[ScopeEntityInterface],
        user_identifier: str | None = None,
    ) -> AccessTokenEntityInterface:
        """Return a new, unstored token for ``client_entity`` and ``scopes``.

        Args:
            client_entity: The client the token is for.
            scopes: The scopes it was granted, already finalised.
            user_identifier: The resource owner it acts for, or ``None`` when
                the client acts for itself.
        """
        ...

    async def persist_new_access_token(
        self,
        access_token_entity: AccessTokenEntityInterface,
    ) -> None:
        """Store ``access_token_entity``.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When a token of
                that identifier is already stored. The grant answers by
                minting another identifier and trying again.
        """
        ...

    async def revoke_access_token(self, token_id: str) -> None:
        """Stop accepting the access token named ``token_id``.

        Revoking one that is unknown, or already revoked, is not an error:
        what the caller asked for is already true.
        """
        ...

    async def is_access_token_revoked(self, token_id: str) -> bool:
        """Tell whether the access token named ``token_id`` was revoked."""
        ...
