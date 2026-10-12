"""The access-token repository of a deployment that keeps no record at all."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_oauth2_server_core.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)

from xtr_security_oauth2_server.entity.access_token import AccessToken

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.scope_entity_interface import ScopeEntityInterface

__all__ = ["NullAccessTokenRepository"]


@final
class NullAccessTokenRepository(AccessTokenRepositoryInterface):
    """Mints tokens, remembers none of them, and reports none revoked.

    An access token here is a signed document a resource server reads on its
    own, so writing one down buys exactly one thing: the ability to withdraw
    it before it expires. A deployment that does not need that gets this
    instead — no row per token issued, and no lookup on the way in.

    Nothing is ever reported revoked, which is the honest answer rather than a
    convenient one: with no record there is nothing that could have been
    marked, so a token stays good until its expiry. That trade is the whole
    of the decision, and it is why this is a separate repository rather than a
    flag on the real one — nobody reading the wiring can miss it.

    It still asks nothing of the application and announces nothing: there are
    no extra claims here, because the event that collects them exists so a
    listener can enrich a token that will be *stored and revocable*, and a
    deployment choosing this one has already said it wants no such machinery
    in the path. A deployment wanting both stores its tokens.
    """

    @override
    def __repr__(self) -> str:
        """Name the type, which is the whole of what there is to say."""
        return f"{type(self).__name__}()"

    @override
    async def get_new_token(
        self,
        client_entity: ClientEntityInterface,
        scopes: Sequence[ScopeEntityInterface],
        user_identifier: str | None = None,
    ) -> AccessTokenEntityInterface:
        """Return a new token for ``client_entity`` and ``scopes``."""
        token = AccessToken()
        token.set_client(client_entity)
        if user_identifier:
            token.set_user_identifier(user_identifier)
        for scope in scopes:
            token.add_scope(scope)

        return token

    @override
    async def persist_new_access_token(
        self,
        access_token_entity: AccessTokenEntityInterface,
    ) -> None:
        """Do nothing: this deployment keeps no record of its access tokens."""
        del access_token_entity

    @override
    async def revoke_access_token(self, token_id: str) -> None:
        """Do nothing: there is no record to mark."""
        del token_id

    @override
    async def is_access_token_revoked(self, token_id: str) -> bool:
        """Return ``False``: with no record, nothing could have been withdrawn."""
        del token_id

        return False
