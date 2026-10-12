"""The client-storage contract is runtime-checkable and fully async."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from tests.support.entities import make_client
from xtr_security_oauth2_server.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface


@final
class _ClientRepository:
    """Holds one client, and accepts its secret for any grant."""

    async def get_client_entity(self, client_identifier: str) -> ClientEntityInterface | None:
        return make_client(client_identifier)

    async def validate_client(
        self,
        client_identifier: str,
        client_secret: str | None,
        grant_type: str | None,
    ) -> bool:
        del client_identifier, grant_type
        return client_secret == "secret"


@final
class _WithoutValidateClient:
    """A repository that can find a client but cannot authenticate one."""

    async def get_client_entity(self, client_identifier: str) -> ClientEntityInterface | None:
        del client_identifier
        return None


def test_a_full_repository_satisfies_the_contract() -> None:
    repository: ClientRepositoryInterface = _ClientRepository()
    assert isinstance(repository, ClientRepositoryInterface)


def test_a_repository_missing_a_method_does_not_satisfy_it() -> None:
    assert not isinstance(_WithoutValidateClient(), ClientRepositoryInterface)
