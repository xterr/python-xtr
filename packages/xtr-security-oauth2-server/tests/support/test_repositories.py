"""The in-memory repositories really satisfy the contracts they stand in for.

A fake is only worth trusting while it behaves like the thing it replaces, so
each one is checked against its contract here: it answers the protocol, it
gives back what it was given, and the few behaviours a grant actually depends
on — revocation, the opt-out, the taken identifier — do what the contract says.
"""

from __future__ import annotations

import pytest

from tests.support.entities import make_client, make_scope, make_user
from tests.support.repositories import (
    InMemoryAccessTokenRepository,
    InMemoryAuthCodeRepository,
    InMemoryClientRepository,
    InMemoryDeviceCodeRepository,
    InMemoryRefreshTokenRepository,
    InMemoryScopeRepository,
    InMemoryUserRepository,
)
from xtr_security_oauth2_server.exception import UniqueTokenIdentifierConstraintViolationError
from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.auth_code_repository_interface import (
    AuthCodeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.device_code_repository_interface import (
    DeviceCodeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.scope_repository_interface import (
    ScopeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.user_repository_interface import (
    UserRepositoryInterface,
)


def test_every_fake_satisfies_the_contract_it_stands_for() -> None:
    assert isinstance(InMemoryClientRepository(), ClientRepositoryInterface)
    assert isinstance(InMemoryAccessTokenRepository(), AccessTokenRepositoryInterface)
    assert isinstance(InMemoryAuthCodeRepository(), AuthCodeRepositoryInterface)
    assert isinstance(InMemoryRefreshTokenRepository(), RefreshTokenRepositoryInterface)
    assert isinstance(InMemoryScopeRepository(), ScopeRepositoryInterface)
    assert isinstance(InMemoryUserRepository(), UserRepositoryInterface)
    assert isinstance(InMemoryDeviceCodeRepository(), DeviceCodeRepositoryInterface)


@pytest.mark.anyio
async def test_a_registered_client_is_found_again() -> None:
    repository = InMemoryClientRepository()
    client = make_client("client-1")
    repository.add(client, "secret")

    assert await repository.get_client_entity("client-1") is client


@pytest.mark.anyio
async def test_an_unregistered_client_is_not_found() -> None:
    assert await InMemoryClientRepository().get_client_entity("nobody") is None


@pytest.mark.anyio
async def test_a_client_authenticates_with_the_secret_it_registered() -> None:
    repository = InMemoryClientRepository()
    repository.add(make_client("client-1"), "secret")

    assert await repository.validate_client("client-1", "secret", "client_credentials") is True


@pytest.mark.anyio
async def test_a_client_does_not_authenticate_with_another_secret() -> None:
    repository = InMemoryClientRepository()
    repository.add(make_client("client-1"), "secret")

    assert await repository.validate_client("client-1", "guess", "client_credentials") is False


@pytest.mark.anyio
async def test_a_client_does_not_authenticate_for_a_grant_it_may_not_use() -> None:
    repository = InMemoryClientRepository()
    repository.add(make_client("client-1"), "secret", grant_types=("authorization_code",))

    assert await repository.validate_client("client-1", "secret", "password") is False


@pytest.mark.anyio
async def test_a_new_access_token_carries_the_client_the_scopes_and_the_owner() -> None:
    repository = InMemoryAccessTokenRepository()
    client = make_client()

    token = await repository.get_new_token(client, (make_scope("read"),), "user-1")

    assert token.get_client() is client
    assert [scope.get_identifier() for scope in token.get_scopes()] == ["read"]
    assert token.get_user_identifier() == "user-1"


@pytest.mark.anyio
async def test_a_stored_access_token_is_not_revoked_until_it_is() -> None:
    repository = InMemoryAccessTokenRepository()
    token = await repository.get_new_token(make_client(), ())
    token.set_identifier("token-1")
    await repository.persist_new_access_token(token)

    assert await repository.is_access_token_revoked("token-1") is False

    await repository.revoke_access_token("token-1")

    assert await repository.is_access_token_revoked("token-1") is True


@pytest.mark.anyio
async def test_an_owed_collision_makes_the_next_store_report_a_taken_identifier() -> None:
    repository = InMemoryAccessTokenRepository()
    repository.collisions.remaining = 1
    token = await repository.get_new_token(make_client(), ())
    token.set_identifier("token-1")

    with pytest.raises(UniqueTokenIdentifierConstraintViolationError):
        await repository.persist_new_access_token(token)

    await repository.persist_new_access_token(token)

    assert repository.tokens["token-1"] is token


@pytest.mark.anyio
async def test_a_redeemed_authorization_code_reports_itself_revoked() -> None:
    repository = InMemoryAuthCodeRepository()
    code = await repository.get_new_auth_code()
    code.set_identifier("code-1")
    await repository.persist_new_auth_code(code)

    await repository.revoke_auth_code("code-1")

    assert await repository.is_auth_code_revoked("code-1") is True


@pytest.mark.anyio
async def test_only_the_first_revocation_of_a_refresh_token_reports_that_it_won() -> None:
    repository = InMemoryRefreshTokenRepository()

    assert await repository.revoke_refresh_token("token-1") is True
    assert await repository.revoke_refresh_token("token-1") is False


@pytest.mark.anyio
async def test_a_repository_that_issues_no_refresh_tokens_mints_none() -> None:
    assert await InMemoryRefreshTokenRepository(issues=False).get_new_refresh_token() is None


@pytest.mark.anyio
async def test_a_known_scope_is_found_and_an_unknown_one_is_not() -> None:
    repository = InMemoryScopeRepository("read", "write")

    found = await repository.get_scope_entity_by_identifier("read")

    assert found is not None
    assert found.get_identifier() == "read"
    assert await repository.get_scope_entity_by_identifier("delete") is None


@pytest.mark.anyio
async def test_finalising_records_the_call_and_answers_what_was_asked_for() -> None:
    repository = InMemoryScopeRepository("read")
    client = make_client()
    scopes = (make_scope("read"),)

    answered = await repository.finalize_scopes(scopes, "password", client, "user-1", "code-1")

    assert tuple(answered) == scopes
    call = repository.finalized[0]
    assert call.grant_type == "password"
    assert call.client_entity is client
    assert call.user_identifier == "user-1"
    assert call.auth_code_id == "code-1"


@pytest.mark.anyio
async def test_finalising_answers_the_override_set_when_one_is_given() -> None:
    repository = InMemoryScopeRepository("read", "write")
    repository.grants = (make_scope("write"),)

    answered = await repository.finalize_scopes((make_scope("read"),), "password", make_client())

    assert [scope.get_identifier() for scope in answered] == ["write"]


@pytest.mark.anyio
async def test_the_right_credentials_find_the_user_and_the_wrong_ones_find_nobody() -> None:
    repository = InMemoryUserRepository()
    user = make_user("user-1")
    repository.add("alice", "password", user)
    client = make_client()

    assert (
        await repository.get_user_entity_by_user_credentials(
            "alice", "password", "password", client
        )
        is user
    )
    assert (
        await repository.get_user_entity_by_user_credentials("alice", "guess", "password", client)
        is None
    )
    assert repository.asked[0].client_identifier == client.get_identifier()


@pytest.mark.anyio
async def test_a_stored_device_code_is_found_by_its_identifier_and_can_be_revoked() -> None:
    repository = InMemoryDeviceCodeRepository()
    code = await repository.get_new_device_code()
    code.set_identifier("device-1")
    await repository.persist_device_code(code)

    assert await repository.get_device_code_entity_by_device_code("device-1") is code
    assert await repository.is_device_code_revoked("device-1") is False

    await repository.revoke_device_code("device-1")

    assert await repository.is_device_code_revoked("device-1") is True
