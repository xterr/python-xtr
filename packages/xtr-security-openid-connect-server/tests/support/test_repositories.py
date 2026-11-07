"""The in-memory repositories really keep the contracts they stand in for.

A fake is only worth trusting while it behaves like the storage it replaces:
each one satisfies its protocol, answers from what it stored, and remembers what
was revoked.
"""

from __future__ import annotations

import pytest
from xtr_security_oauth2_server.entity import Client
from xtr_security_oauth2_server_core.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.auth_code_repository_interface import (
    AuthCodeRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.scope_repository_interface import (
    ScopeRepositoryInterface,
)

from tests.support.repositories import (
    InMemoryAccessTokenRepository,
    InMemoryAuthCodeRepository,
    InMemoryClientRepository,
    InMemoryRefreshTokenRepository,
    InMemoryScopeRepository,
)

pytestmark = pytest.mark.anyio


def _client() -> Client:
    client = Client()
    client.set_identifier("my-client")
    return client


def test_each_satisfies_its_storage_contract() -> None:
    assert isinstance(InMemoryClientRepository(), ClientRepositoryInterface)
    assert isinstance(InMemoryAccessTokenRepository(), AccessTokenRepositoryInterface)
    assert isinstance(InMemoryAuthCodeRepository(), AuthCodeRepositoryInterface)
    assert isinstance(InMemoryRefreshTokenRepository(), RefreshTokenRepositoryInterface)
    assert isinstance(InMemoryScopeRepository(), ScopeRepositoryInterface)


async def test_a_client_is_found_and_proves_its_secret() -> None:
    clients = InMemoryClientRepository()
    client = _client()
    clients.add(client, "s3cret")

    assert await clients.get_client_entity("my-client") is client
    assert await clients.get_client_entity("other") is None
    assert await clients.validate_client("my-client", "s3cret", None)
    assert not await clients.validate_client("my-client", "wrong", None)


async def test_an_access_token_is_minted_for_its_owner_stored_and_revoked() -> None:
    tokens = InMemoryAccessTokenRepository()
    scopes = InMemoryScopeRepository("openid")
    openid = await scopes.get_scope_entity_by_identifier("openid")
    assert openid is not None

    token = await tokens.get_new_token(_client(), [openid], "alice")
    token.set_identifier("access-1")
    await tokens.persist_new_access_token(token)
    await tokens.revoke_access_token("access-1")

    assert token.get_user_identifier() == "alice"
    assert [scope.get_identifier() for scope in token.get_scopes()] == ["openid"]
    assert tokens.tokens == {"access-1": token}
    assert await tokens.is_access_token_revoked("access-1")


async def test_a_token_minted_for_no_owner_carries_none() -> None:
    token = await InMemoryAccessTokenRepository().get_new_token(_client(), [])

    assert token.get_user_identifier() is None


async def test_an_auth_code_is_stored_and_revoked() -> None:
    codes = InMemoryAuthCodeRepository()
    code = await codes.get_new_auth_code()
    code.set_identifier("code-1")
    await codes.persist_new_auth_code(code)

    assert not await codes.is_auth_code_revoked("code-1")
    await codes.revoke_auth_code("code-1")
    assert await codes.is_auth_code_revoked("code-1")
    assert codes.codes == {"code-1": code}


async def test_a_refresh_token_is_revoked_once() -> None:
    tokens = InMemoryRefreshTokenRepository()
    token = await tokens.get_new_refresh_token()
    assert token is not None
    token.set_identifier("refresh-1")
    await tokens.persist_new_refresh_token(token)

    assert await tokens.revoke_refresh_token("refresh-1")
    assert not await tokens.revoke_refresh_token("refresh-1")
    assert await tokens.is_refresh_token_revoked("refresh-1")
    assert tokens.tokens == {"refresh-1": token}


async def test_scopes_are_known_by_name_and_granted_as_asked() -> None:
    scopes = InMemoryScopeRepository("openid", "profile")
    openid = await scopes.get_scope_entity_by_identifier("openid")
    assert openid is not None

    assert await scopes.get_scope_entity_by_identifier("email") is None
    assert await scopes.finalize_scopes([openid], "authorization_code", _client()) == (openid,)
