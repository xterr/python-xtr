"""Minting an authorization code, storing it, and ending its life on redemption."""

from __future__ import annotations

import pytest
from xtr_clock import MockClock

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entity_builders import auth_code_entity, client_entity
from tests.support.models import NOW, client_model
from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.exception import (
    UniqueTokenIdentifierConstraintViolationError,
)
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.manager.in_memory.authorization_code_manager import (
    AuthorizationCodeManager,
)
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.repositories.auth_code_repository_interface import (
    AuthCodeRepositoryInterface,
)
from xtr_security_oauth2_server.repository.auth_code_repository import AuthCodeRepository
from xtr_security_oauth2_server.value_object.scope import Scope

pytestmark = pytest.mark.anyio


async def _repository() -> tuple[AuthCodeRepository, AuthorizationCodeManager]:
    codes = AuthorizationCodeManager(MockClock(NOW))
    clients = ClientManager(RecordingEventDispatcher())
    await clients.save(client_model("client-1"))

    return AuthCodeRepository(codes, clients, ScopeConverter()), codes


async def test_it_satisfies_the_auth_code_repository_contract() -> None:
    repository, _ = await _repository()

    assert AuthCodeRepositoryInterface in AuthCodeRepository.__mro__
    assert isinstance(repository, AuthCodeRepositoryInterface)


async def test_it_mints_an_unfilled_code() -> None:
    repository, _ = await _repository()

    minted = await repository.get_new_auth_code()

    assert minted.get_redirect_uri() is None


async def test_it_stores_what_was_issued() -> None:
    repository, codes = await _repository()

    await repository.persist_new_auth_code(auth_code_entity(scopes=("read",)))

    stored = await codes.find("ac-1")
    assert stored is not None
    assert stored.get_scopes() == (Scope("read"),)
    assert stored.get_user_identifier() == "user-1"
    assert stored.get_client().get_identifier() == "client-1"


async def test_it_refuses_an_identifier_already_taken() -> None:
    repository, _ = await _repository()
    await repository.persist_new_auth_code(auth_code_entity())

    with pytest.raises(UniqueTokenIdentifierConstraintViolationError):
        await repository.persist_new_auth_code(auth_code_entity())


async def test_it_refuses_to_store_a_code_for_a_client_nobody_stored() -> None:
    repository, _ = await _repository()
    entity = auth_code_entity(client=client_entity("unknown-client"))

    with pytest.raises(InvalidArgumentError, match="unknown-client"):
        await repository.persist_new_auth_code(entity)


async def test_it_withdraws_a_code_it_stored() -> None:
    repository, codes = await _repository()
    await repository.persist_new_auth_code(auth_code_entity())

    await repository.revoke_auth_code("ac-1")

    stored = await codes.find("ac-1")
    assert stored is not None
    assert stored.is_revoked() is True


async def test_withdrawing_a_code_it_never_stored_is_no_error() -> None:
    repository, _ = await _repository()

    await repository.revoke_auth_code("nope")


async def test_a_code_it_never_stored_counts_as_withdrawn() -> None:
    repository, _ = await _repository()

    assert await repository.is_auth_code_revoked("nope") is True


async def test_a_code_it_stored_is_not_withdrawn() -> None:
    repository, _ = await _repository()
    await repository.persist_new_auth_code(auth_code_entity())

    assert await repository.is_auth_code_revoked("ac-1") is False


async def test_a_code_it_withdrew_reports_as_withdrawn() -> None:
    repository, _ = await _repository()
    await repository.persist_new_auth_code(auth_code_entity())

    await repository.revoke_auth_code("ac-1")

    assert await repository.is_auth_code_revoked("ac-1") is True
