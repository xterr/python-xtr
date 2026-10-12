"""The resource-owner storage contract checks credentials and is async."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from tests.support.entities import make_user
from xtr_security_oauth2_server_core.repositories.user_repository_interface import (
    UserRepositoryInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.user_entity_interface import UserEntityInterface


@final
class _UserRepository:
    """Accepts one pair of credentials, whatever grant or client asks."""

    async def get_user_entity_by_user_credentials(
        self,
        username: str,
        password: str,
        grant_type: str,
        client_entity: ClientEntityInterface,
    ) -> UserEntityInterface | None:
        del grant_type, client_entity
        if (username, password) != ("owner", "secret"):
            return None
        return make_user(username)


@final
class _Nothing:
    """A class that checks no credentials."""


def test_a_full_repository_satisfies_the_contract() -> None:
    repository: UserRepositoryInterface = _UserRepository()
    assert isinstance(repository, UserRepositoryInterface)


def test_a_repository_missing_the_method_does_not_satisfy_it() -> None:
    assert not isinstance(_Nothing(), UserRepositoryInterface)
