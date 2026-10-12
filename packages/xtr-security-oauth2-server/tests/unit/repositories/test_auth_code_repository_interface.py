"""The authorization-code storage contract is runtime-checkable and fully async."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from tests.support.entities import AuthCode
from xtr_security_oauth2_server.repositories.auth_code_repository_interface import (
    AuthCodeRepositoryInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server.entities.auth_code_entity_interface import (
        AuthCodeEntityInterface,
    )


@final
class _AuthCodeRepository:
    """Keeps the codes it was handed, and the ids it was told to revoke."""

    def __init__(self) -> None:
        self.revoked: set[str] = set()

    async def get_new_auth_code(self) -> AuthCodeEntityInterface:
        return AuthCode()

    async def persist_new_auth_code(self, auth_code_entity: AuthCodeEntityInterface) -> None:
        del auth_code_entity

    async def revoke_auth_code(self, code_id: str) -> None:
        self.revoked.add(code_id)

    async def is_auth_code_revoked(self, code_id: str) -> bool:
        return code_id in self.revoked


@final
class _WithoutPersist:
    """A repository that mints a code but cannot store one."""

    async def get_new_auth_code(self) -> AuthCodeEntityInterface:
        return AuthCode()

    async def revoke_auth_code(self, code_id: str) -> None:
        del code_id

    async def is_auth_code_revoked(self, code_id: str) -> bool:
        del code_id
        return False


def test_a_full_repository_satisfies_the_contract() -> None:
    repository: AuthCodeRepositoryInterface = _AuthCodeRepository()
    assert isinstance(repository, AuthCodeRepositoryInterface)


def test_a_repository_missing_a_method_does_not_satisfy_it() -> None:
    assert not isinstance(_WithoutPersist(), AuthCodeRepositoryInterface)
