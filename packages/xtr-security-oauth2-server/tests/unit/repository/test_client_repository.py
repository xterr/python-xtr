"""Whether a client proved who it is, and the upgrade a successful proof triggers."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_password_hasher.hasher.plaintext_password_hasher import PlaintextPasswordHasher

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.hashers import RecordingPasswordHasher
from tests.support.models import client_model
from xtr_security_oauth2_server.entity.client import Client as ClientEntity
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)
from xtr_security_oauth2_server.repository.client_repository import ClientRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.manager.client_filter import ClientFilter
    from xtr_security_oauth2_server.model.client_interface import ClientInterface

pytestmark = pytest.mark.anyio


@final
class _ManagerThatCannotSave:
    """Holds one client and cannot write, the way a store gone away behaves."""

    def __init__(self, client: ClientInterface) -> None:
        self._client = client

    async def find(self, identifier: str) -> ClientInterface | None:
        return self._client if identifier == self._client.get_identifier() else None

    async def save(self, client: ClientInterface) -> None:
        del client
        message = "the store is unreachable"
        raise RuntimeError(message)

    async def remove(self, client: ClientInterface) -> None:
        del client

    async def list(self, client_filter: ClientFilter | None) -> Sequence[ClientInterface]:
        del client_filter

        return (self._client,)


async def _manager(client: ClientInterface | None = None) -> ClientManager:
    manager = ClientManager(RecordingEventDispatcher())
    if client is not None:
        await manager.save(client)

    return manager


async def _repository(
    client: ClientInterface | None = None,
    hasher: RecordingPasswordHasher | None = None,
) -> tuple[ClientRepository, ClientManager]:
    manager = await _manager(client)
    held = hasher if hasher is not None else RecordingPasswordHasher()

    return ClientRepository(manager, held), manager


async def test_it_satisfies_the_client_repository_contract() -> None:
    repository, _ = await _repository()

    assert ClientRepositoryInterface in ClientRepository.__mro__
    assert isinstance(repository, ClientRepositoryInterface)


async def test_it_finds_no_entity_for_a_client_nobody_registered() -> None:
    repository, _ = await _repository()

    assert await repository.get_client_entity("nope") is None


async def test_it_builds_the_entity_a_grant_reads_from_the_registration() -> None:
    stored = client_model(
        "client-1",
        name="Test client",
        grants=("authorization_code",),
        redirect_uris=("https://a.example.com/cb",),
    )
    repository, _ = await _repository(stored)

    entity = await repository.get_client_entity("client-1")

    assert entity is not None
    assert entity.get_identifier() == "client-1"
    assert entity.get_name() == "Test client"
    assert entity.get_redirect_uri() == ("https://a.example.com/cb",)
    assert entity.is_confidential() is True
    assert entity.supports_grant_type("authorization_code") is True
    assert entity.supports_grant_type("password") is False


async def test_the_entity_of_a_client_allowed_plain_pkce_says_so() -> None:
    stored = client_model()
    _ = stored.set_allow_plain_text_pkce(True)
    repository, _ = await _repository(stored)

    entity = await repository.get_client_entity("client-1")

    assert isinstance(entity, ClientEntity)
    assert entity.is_plain_text_pkce_allowed() is True


async def test_the_entity_of_a_public_client_says_it_keeps_no_secret() -> None:
    repository, _ = await _repository(client_model(secret=None))

    entity = await repository.get_client_entity("client-1")

    assert entity is not None
    assert entity.is_confidential() is False


async def test_it_refuses_a_client_nobody_registered() -> None:
    repository, _ = await _repository()

    assert await repository.validate_client("nope", "s3cret", "client_credentials") is False


async def test_it_refuses_a_client_that_was_deactivated() -> None:
    hasher = RecordingPasswordHasher()
    stored = client_model(secret=hasher.hash("s3cret"), active=False)
    repository, _ = await _repository(stored, hasher)

    assert await repository.validate_client("client-1", "s3cret", "client_credentials") is False


async def test_it_refuses_a_grant_the_client_was_not_registered_for() -> None:
    hasher = RecordingPasswordHasher()
    stored = client_model(secret=hasher.hash("s3cret"), grants=("authorization_code",))
    repository, _ = await _repository(stored, hasher)

    assert await repository.validate_client("client-1", "s3cret", "password") is False


async def test_it_allows_any_grant_to_a_client_registered_for_none() -> None:
    hasher = RecordingPasswordHasher()
    repository, _ = await _repository(client_model(secret=hasher.hash("s3cret")), hasher)

    assert await repository.validate_client("client-1", "s3cret", "password") is True


async def test_it_allows_a_caller_acting_for_no_grant_in_particular() -> None:
    hasher = RecordingPasswordHasher()
    stored = client_model(secret=hasher.hash("s3cret"), grants=("authorization_code",))
    repository, _ = await _repository(stored, hasher)

    assert await repository.validate_client("client-1", "s3cret", None) is True


async def test_it_refuses_the_wrong_secret() -> None:
    hasher = RecordingPasswordHasher()
    repository, _ = await _repository(client_model(secret=hasher.hash("s3cret")), hasher)

    assert await repository.validate_client("client-1", "wrong", "client_credentials") is False


async def test_it_refuses_a_confidential_client_that_sent_no_secret() -> None:
    hasher = RecordingPasswordHasher()
    repository, _ = await _repository(client_model(secret=hasher.hash("s3cret")), hasher)

    assert await repository.validate_client("client-1", None, "client_credentials") is False


async def test_it_accepts_the_right_secret() -> None:
    hasher = RecordingPasswordHasher()
    repository, _ = await _repository(client_model(secret=hasher.hash("s3cret")), hasher)

    assert await repository.validate_client("client-1", "s3cret", "client_credentials") is True


async def test_a_public_client_proves_nothing_and_is_accepted() -> None:
    repository, _ = await _repository(client_model(secret=None))

    assert await repository.validate_client("client-1", None, "authorization_code") is True


async def test_a_public_client_is_accepted_even_if_it_sent_something() -> None:
    repository, _ = await _repository(client_model(secret=None))

    assert await repository.validate_client("client-1", "anything", "authorization_code") is True


async def test_it_compares_a_secret_only_through_the_hasher() -> None:
    hasher = RecordingPasswordHasher()
    repository, _ = await _repository(client_model(secret="s3cret"), hasher)

    accepted = await repository.validate_client("client-1", "s3cret", "client_credentials")

    assert accepted is False
    assert hasher.verify_calls == 1


async def test_it_upgrades_a_stale_hash_after_a_successful_proof() -> None:
    hasher = RecordingPasswordHasher()
    repository, manager = await _repository(client_model(secret="v1$s3cret"), hasher)

    accepted = await repository.validate_client("client-1", "s3cret", "client_credentials")

    stored = await manager.find("client-1")
    assert accepted is True
    assert stored is not None
    assert stored.get_secret() == "v2$s3cret"


async def test_it_leaves_a_current_hash_alone() -> None:
    hasher = RecordingPasswordHasher()
    repository, _ = await _repository(client_model(secret=hasher.hash("s3cret")), hasher)
    hasher.hash_calls = 0

    _ = await repository.validate_client("client-1", "s3cret", "client_credentials")

    assert hasher.hash_calls == 0


async def test_it_upgrades_nothing_after_a_failed_proof() -> None:
    hasher = RecordingPasswordHasher()
    repository, manager = await _repository(client_model(secret="v1$s3cret"), hasher)

    _ = await repository.validate_client("client-1", "wrong", "client_credentials")

    stored = await manager.find("client-1")
    assert stored is not None
    assert stored.get_secret() == "v1$s3cret"


async def test_a_failed_upgrade_does_not_fail_an_otherwise_valid_proof() -> None:
    repository = ClientRepository(
        _ManagerThatCannotSave(client_model(secret="v1$s3cret")),
        RecordingPasswordHasher(),
    )

    assert await repository.validate_client("client-1", "s3cret", "client_credentials") is True


async def test_it_works_with_whichever_hasher_the_deployment_configured() -> None:
    manager = await _manager(client_model(secret="s3cret"))
    repository = ClientRepository(manager, PlaintextPasswordHasher())

    assert await repository.validate_client("client-1", "s3cret", "client_credentials") is True
