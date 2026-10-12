"""Minting a refresh token, storing it, and withdrawing it exactly once."""

from __future__ import annotations

import pytest
from xtr_clock import MockClock

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entity_builders import access_token_entity, refresh_token_entity
from tests.support.models import NOW, client_model
from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.exception import (
    UniqueTokenIdentifierConstraintViolationError,
)
from xtr_security_oauth2_server.manager.in_memory.access_token_manager import AccessTokenManager
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.manager.in_memory.refresh_token_manager import RefreshTokenManager
from xtr_security_oauth2_server.manager.null.access_token_manager import (
    AccessTokenManager as NullAccessTokenManager,
)
from xtr_security_oauth2_server.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from xtr_security_oauth2_server.repository.access_token_repository import AccessTokenRepository
from xtr_security_oauth2_server.repository.refresh_token_repository import RefreshTokenRepository

pytestmark = pytest.mark.anyio


async def _repository() -> tuple[RefreshTokenRepository, RefreshTokenManager, AccessTokenManager]:
    access_tokens = AccessTokenManager(MockClock(NOW))
    refresh_tokens = RefreshTokenManager(MockClock(NOW))
    clients = ClientManager(RecordingEventDispatcher())
    await clients.save(client_model("client-1"))
    access_token_repository = AccessTokenRepository(
        access_tokens,
        clients,
        ScopeConverter(),
        RecordingEventDispatcher(),
    )
    await access_token_repository.persist_new_access_token(access_token_entity())

    return (
        RefreshTokenRepository(refresh_tokens, access_tokens),
        refresh_tokens,
        access_tokens,
    )


async def test_it_satisfies_the_refresh_token_repository_contract() -> None:
    repository, _, _ = await _repository()

    assert RefreshTokenRepositoryInterface in RefreshTokenRepository.__mro__
    assert isinstance(repository, RefreshTokenRepositoryInterface)


async def test_it_mints_an_unfilled_refresh_token() -> None:
    repository, _, _ = await _repository()

    minted = await repository.get_new_refresh_token()

    assert minted is not None
    assert repr(minted) == "RefreshToken(identifier=unset)"


async def test_it_stores_what_was_issued() -> None:
    repository, refresh_tokens, _ = await _repository()

    await repository.persist_new_refresh_token(refresh_token_entity())

    stored = await refresh_tokens.find("rt-1")
    assert stored is not None
    assert stored.get_identifier() == "rt-1"


async def test_it_ties_the_stored_token_to_the_stored_access_token() -> None:
    repository, refresh_tokens, _ = await _repository()

    await repository.persist_new_refresh_token(refresh_token_entity())

    stored = await refresh_tokens.find("rt-1")
    assert stored is not None
    access_token = stored.get_access_token()
    assert access_token is not None
    assert access_token.get_identifier() == "at-1"


async def test_it_stores_a_token_beside_an_access_token_nobody_kept() -> None:
    refresh_tokens = RefreshTokenManager(MockClock(NOW))
    repository = RefreshTokenRepository(refresh_tokens, NullAccessTokenManager())

    await repository.persist_new_refresh_token(refresh_token_entity())

    stored = await refresh_tokens.find("rt-1")
    assert stored is not None
    assert stored.get_access_token() is None


async def test_it_refuses_an_identifier_already_taken() -> None:
    repository, _, _ = await _repository()
    await repository.persist_new_refresh_token(refresh_token_entity())

    with pytest.raises(UniqueTokenIdentifierConstraintViolationError):
        await repository.persist_new_refresh_token(refresh_token_entity())


async def test_the_caller_that_withdraws_a_token_is_told_it_did() -> None:
    repository, _, _ = await _repository()
    await repository.persist_new_refresh_token(refresh_token_entity())

    assert await repository.revoke_refresh_token("rt-1") is True


async def test_a_second_caller_withdrawing_the_same_token_is_told_it_did_not() -> None:
    repository, _, _ = await _repository()
    await repository.persist_new_refresh_token(refresh_token_entity())
    _ = await repository.revoke_refresh_token("rt-1")

    assert await repository.revoke_refresh_token("rt-1") is False


async def test_withdrawing_a_token_it_never_stored_is_told_it_withdrew_nothing() -> None:
    repository, _, _ = await _repository()

    assert await repository.revoke_refresh_token("nope") is False


async def test_a_token_it_never_stored_counts_as_withdrawn() -> None:
    repository, _, _ = await _repository()

    assert await repository.is_refresh_token_revoked("nope") is True


async def test_a_token_it_stored_is_not_withdrawn() -> None:
    repository, _, _ = await _repository()
    await repository.persist_new_refresh_token(refresh_token_entity())

    assert await repository.is_refresh_token_revoked("rt-1") is False


async def test_a_token_it_withdrew_reports_as_withdrawn() -> None:
    repository, _, _ = await _repository()
    await repository.persist_new_refresh_token(refresh_token_entity())

    _ = await repository.revoke_refresh_token("rt-1")

    assert await repository.is_refresh_token_revoked("rt-1") is True
