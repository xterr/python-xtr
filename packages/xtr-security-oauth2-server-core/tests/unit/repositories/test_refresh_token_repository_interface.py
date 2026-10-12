"""The refresh-token storage contract revokes atomically and says who won."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from tests.support.entities import RefreshToken
from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )


@final
class _RefreshTokenRepository:
    """Revokes by check-and-set, so only the first caller is told it won."""

    def __init__(self) -> None:
        self.revoked: set[str] = set()

    async def get_new_refresh_token(self) -> RefreshTokenEntityInterface | None:
        return RefreshToken()

    async def persist_new_refresh_token(
        self,
        refresh_token_entity: RefreshTokenEntityInterface,
    ) -> None:
        del refresh_token_entity

    async def revoke_refresh_token(self, token_id: str) -> bool:
        if token_id in self.revoked:
            return False
        self.revoked.add(token_id)
        return True

    async def is_refresh_token_revoked(self, token_id: str) -> bool:
        return token_id in self.revoked


@final
class _WithoutNewToken:
    """A repository that stores refresh tokens but cannot mint one."""

    async def persist_new_refresh_token(
        self,
        refresh_token_entity: RefreshTokenEntityInterface,
    ) -> None:
        del refresh_token_entity

    async def revoke_refresh_token(self, token_id: str) -> bool:
        del token_id
        return True

    async def is_refresh_token_revoked(self, token_id: str) -> bool:
        del token_id
        return False


def test_a_full_repository_satisfies_the_contract() -> None:
    repository: RefreshTokenRepositoryInterface = _RefreshTokenRepository()
    assert isinstance(repository, RefreshTokenRepositoryInterface)


def test_a_repository_missing_a_method_does_not_satisfy_it() -> None:
    assert not isinstance(_WithoutNewToken(), RefreshTokenRepositoryInterface)


@pytest.mark.anyio
async def test_the_first_revocation_of_a_token_reports_that_it_revoked_it() -> None:
    repository: RefreshTokenRepositoryInterface = _RefreshTokenRepository()

    assert await repository.revoke_refresh_token("token-1") is True


@pytest.mark.anyio
async def test_revoking_an_already_revoked_token_reports_that_it_did_not() -> None:
    repository: RefreshTokenRepositoryInterface = _RefreshTokenRepository()
    _ = await repository.revoke_refresh_token("token-1")

    assert await repository.revoke_refresh_token("token-1") is False
