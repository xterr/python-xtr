"""The one credential this server reads back: a device code, poll after poll."""

from __future__ import annotations

import pytest
from xtr_clock import MockClock
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.repositories.device_code_repository_interface import (
    DeviceCodeRepositoryInterface,
)

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entity_builders import client_entity, device_code_entity
from tests.support.hashers import RecordingPasswordHasher
from tests.support.models import NOW, client_model
from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.manager.in_memory.device_code_manager import DeviceCodeManager
from xtr_security_oauth2_server.repository.client_repository import ClientRepository
from xtr_security_oauth2_server.repository.device_code_repository import DeviceCodeRepository
from xtr_security_oauth2_server.value_object.scope import Scope

pytestmark = pytest.mark.anyio

_POLLED_AT = NOW


async def _repository() -> tuple[DeviceCodeRepository, DeviceCodeManager]:
    codes = DeviceCodeManager(MockClock(NOW))
    clients = ClientManager(RecordingEventDispatcher())
    await clients.save(client_model("client-1", name="Stored client"))
    client_repository = ClientRepository(clients, RecordingPasswordHasher())

    return (
        DeviceCodeRepository(codes, clients, ScopeConverter(), client_repository),
        codes,
    )


async def test_it_satisfies_the_device_code_repository_contract() -> None:
    repository, _ = await _repository()

    assert DeviceCodeRepositoryInterface in DeviceCodeRepository.__mro__
    assert isinstance(repository, DeviceCodeRepositoryInterface)


async def test_it_mints_an_unapproved_code() -> None:
    repository, _ = await _repository()

    minted = await repository.get_new_device_code()

    assert minted.get_user_approved() is False


async def test_it_stores_what_was_issued() -> None:
    repository, codes = await _repository()

    await repository.persist_device_code(device_code_entity(scopes=("read",)))

    stored = await codes.find("dc-1")
    assert stored is not None
    assert stored.get_user_code() == "BCDFGHJK"
    assert stored.get_scopes() == (Scope("read"),)
    assert stored.get_interval() == 5
    assert stored.get_client().get_identifier() == "client-1"


async def test_it_stores_that_the_pre_filled_uri_was_asked_for() -> None:
    repository, codes = await _repository()

    await repository.persist_device_code(
        device_code_entity(include_verification_uri_complete=True),
    )

    stored = await codes.find("dc-1")
    assert stored is not None
    assert stored.get_include_verification_uri_complete() is True


async def test_it_refuses_to_store_a_code_for_a_client_nobody_stored() -> None:
    repository, _ = await _repository()
    entity = device_code_entity(client=client_entity("unknown-client"))

    with pytest.raises(InvalidArgumentError, match="unknown-client"):
        await repository.persist_device_code(entity)


async def test_storing_a_known_code_again_records_the_poll() -> None:
    repository, codes = await _repository()
    await repository.persist_device_code(device_code_entity())

    await repository.persist_device_code(device_code_entity(last_polled_at=_POLLED_AT))

    stored = await codes.find("dc-1")
    assert stored is not None
    assert stored.get_last_polled_at() == _POLLED_AT


async def test_storing_a_known_code_again_records_the_approval() -> None:
    repository, codes = await _repository()
    await repository.persist_device_code(device_code_entity())

    await repository.persist_device_code(
        device_code_entity(user_identifier="user-1", user_approved=True),
    )

    stored = await codes.find("dc-1")
    assert stored is not None
    assert stored.get_user_identifier() == "user-1"
    assert stored.get_user_approved() is True


async def test_storing_a_known_code_again_leaves_an_unapproved_one_unapproved() -> None:
    repository, codes = await _repository()
    await repository.persist_device_code(device_code_entity(user_approved=True))

    await repository.persist_device_code(device_code_entity(last_polled_at=_POLLED_AT))

    stored = await codes.find("dc-1")
    assert stored is not None
    assert stored.get_user_identifier() is None


async def test_it_finds_nothing_for_a_code_it_never_stored() -> None:
    repository, _ = await _repository()

    assert await repository.get_device_code_entity_by_device_code("nope") is None


async def test_it_builds_the_entity_a_grant_reads_from_what_was_stored() -> None:
    repository, _ = await _repository()
    await repository.persist_device_code(
        device_code_entity(
            scopes=("read",),
            user_identifier="user-1",
            user_approved=True,
            last_polled_at=_POLLED_AT,
            include_verification_uri_complete=True,
        ),
    )

    entity = await repository.get_device_code_entity_by_device_code("dc-1")

    assert entity is not None
    assert entity.get_identifier() == "dc-1"
    assert entity.get_user_code() == "BCDFGHJK"
    assert entity.get_user_approved() is True
    assert entity.get_user_identifier() == "user-1"
    assert entity.get_last_polled_at() == _POLLED_AT
    assert entity.get_interval() == 5
    assert [str(scope) for scope in entity.get_scopes()] == ["read"]
    assert entity.get_client().get_name() == "Stored client"


async def test_the_entity_it_builds_carries_no_poll_when_none_was_made() -> None:
    repository, _ = await _repository()
    await repository.persist_device_code(device_code_entity())

    entity = await repository.get_device_code_entity_by_device_code("dc-1")

    assert entity is not None
    assert entity.get_last_polled_at() is None


async def test_it_withdraws_a_code_it_stored() -> None:
    repository, codes = await _repository()
    await repository.persist_device_code(device_code_entity())

    await repository.revoke_device_code("dc-1")

    stored = await codes.find("dc-1")
    assert stored is not None
    assert stored.is_revoked() is True


async def test_withdrawing_a_code_it_never_stored_is_no_error() -> None:
    repository, _ = await _repository()

    await repository.revoke_device_code("nope")


async def test_a_code_it_never_stored_counts_as_withdrawn() -> None:
    repository, _ = await _repository()

    assert await repository.is_device_code_revoked("nope") is True


async def test_a_code_it_stored_is_not_withdrawn() -> None:
    repository, _ = await _repository()
    await repository.persist_device_code(device_code_entity())

    assert await repository.is_device_code_revoked("dc-1") is False


async def test_a_code_it_withdrew_reports_as_withdrawn() -> None:
    repository, _ = await _repository()
    await repository.persist_device_code(device_code_entity())

    await repository.revoke_device_code("dc-1")

    assert await repository.is_device_code_revoked("dc-1") is True
