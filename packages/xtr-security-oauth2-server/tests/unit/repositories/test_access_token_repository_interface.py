"""The access-token storage contract is runtime-checkable and fully async."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from tests.support.entities import AccessToken
from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface


@final
class _AccessTokenRepository:
    """Keeps the tokens it was handed, and the ids it was told to revoke."""

    def __init__(self) -> None:
        self.stored: list[AccessTokenEntityInterface] = []
        self.revoked: set[str] = set()

    async def get_new_token(
        self,
        client_entity: ClientEntityInterface,
        scopes: Sequence[ScopeEntityInterface],
        user_identifier: str | None = None,
    ) -> AccessTokenEntityInterface:
        token = AccessToken()
        token.set_client(client_entity)
        for scope in scopes:
            token.add_scope(scope)
        if user_identifier is not None:
            token.set_user_identifier(user_identifier)
        return token

    async def persist_new_access_token(
        self,
        access_token_entity: AccessTokenEntityInterface,
    ) -> None:
        self.stored.append(access_token_entity)

    async def revoke_access_token(self, token_id: str) -> None:
        self.revoked.add(token_id)

    async def is_access_token_revoked(self, token_id: str) -> bool:
        return token_id in self.revoked


@final
class _WithoutRevocationCheck:
    """A repository that can revoke a token but cannot be asked about one."""

    async def get_new_token(
        self,
        client_entity: ClientEntityInterface,
        scopes: Sequence[ScopeEntityInterface],
        user_identifier: str | None = None,
    ) -> AccessTokenEntityInterface:
        del client_entity, scopes, user_identifier
        return AccessToken()

    async def persist_new_access_token(
        self,
        access_token_entity: AccessTokenEntityInterface,
    ) -> None:
        del access_token_entity

    async def revoke_access_token(self, token_id: str) -> None:
        del token_id


def test_a_full_repository_satisfies_the_contract() -> None:
    repository: AccessTokenRepositoryInterface = _AccessTokenRepository()
    assert isinstance(repository, AccessTokenRepositoryInterface)


def test_a_repository_missing_a_method_does_not_satisfy_it() -> None:
    assert not isinstance(_WithoutRevocationCheck(), AccessTokenRepositoryInterface)
