"""Minting a refresh token, writing it down, and withdrawing it exactly once."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_oauth2_server_core.exception import (
    UniqueTokenIdentifierConstraintViolationError,
)
from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)

from xtr_security_oauth2_server.entity.refresh_token import RefreshToken as RefreshTokenEntity
from xtr_security_oauth2_server.manager.access_token_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    RefreshTokenManagerInterface,
)
from xtr_security_oauth2_server.model.refresh_token import RefreshToken as RefreshTokenModel

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )

__all__ = ["RefreshTokenRepository"]


@final
class RefreshTokenRepository(RefreshTokenRepositoryInterface):
    """Mints the refresh-token entity, stores it, and withdraws it atomically.

    Withdrawing reports whether *this* call is the one that did it, and that
    is the whole point of the method. Two refreshes of one token can both read
    it as valid; only one of them can be told it revoked it, and the refresh
    grant refuses the other. The manager decides and writes in one step, so
    the window the two would otherwise race through is closed rather than
    narrowed.

    The access-token manager is here to tie the stored refresh token to the
    stored access token, when there is one: a deployment that keeps no access
    tokens still keeps its refresh tokens, and they simply point at nothing.
    """

    def __init__(
        self,
        refresh_token_manager: RefreshTokenManagerInterface,
        access_token_manager: AccessTokenManagerInterface,
    ) -> None:
        """Store refresh tokens and look up access tokens through the managers given."""
        self._refresh_token_manager = refresh_token_manager
        self._access_token_manager = access_token_manager

    @override
    def __repr__(self) -> str:
        """Name the type; the collaborators say nothing a reader needs."""
        return f"{type(self).__name__}()"

    @override
    async def get_new_refresh_token(self) -> RefreshTokenEntityInterface | None:
        """Return a new, unstored refresh token."""
        return RefreshTokenEntity()

    @override
    async def persist_new_refresh_token(
        self,
        refresh_token_entity: RefreshTokenEntityInterface,
    ) -> None:
        """Store ``refresh_token_entity``.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When a token of
                that identifier is already stored.
        """
        identifier = refresh_token_entity.get_identifier()
        if await self._refresh_token_manager.find(identifier) is not None:
            raise UniqueTokenIdentifierConstraintViolationError.create()

        access_token = await self._access_token_manager.find(
            refresh_token_entity.get_access_token().get_identifier(),
        )
        await self._refresh_token_manager.save(
            RefreshTokenModel(
                identifier,
                refresh_token_entity.get_expiry_date_time(),
                access_token,
            ),
        )

    @override
    async def revoke_refresh_token(self, token_id: str) -> bool:
        """Stop accepting the refresh token named ``token_id``.

        Returns:
            Whether this call is what revoked it.
        """
        return await self._refresh_token_manager.revoke(token_id)

    @override
    async def is_refresh_token_revoked(self, token_id: str) -> bool:
        """Tell whether the refresh token named ``token_id`` was revoked.

        A token nobody stored counts as revoked: every refresh token this
        server issues is written down, so one with no record was never issued
        here.
        """
        token = await self._refresh_token_manager.find(token_id)
        if token is None:
            return True

        return token.is_revoked()
