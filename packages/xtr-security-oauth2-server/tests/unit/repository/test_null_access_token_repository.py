"""The access-token repository of a deployment that keeps no record at all."""

from __future__ import annotations

import pytest
from xtr_security_oauth2_server_core.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)

from tests.support.entity_builders import access_token_entity, client_entity, scope_entities
from xtr_security_oauth2_server.repository.null_access_token_repository import (
    NullAccessTokenRepository,
)

pytestmark = pytest.mark.anyio


async def test_it_satisfies_the_access_token_repository_contract() -> None:
    assert AccessTokenRepositoryInterface in NullAccessTokenRepository.__mro__
    assert isinstance(NullAccessTokenRepository(), AccessTokenRepositoryInterface)


async def test_it_mints_a_token_for_the_client_it_was_given() -> None:
    minted = await NullAccessTokenRepository().get_new_token(
        client_entity(),
        scope_entities("read"),
        "user-1",
    )

    assert minted.get_client().get_identifier() == "client-1"
    assert [str(scope) for scope in minted.get_scopes()] == ["read"]
    assert minted.get_user_identifier() == "user-1"


async def test_it_mints_a_token_naming_nobody_when_the_client_acts_for_itself() -> None:
    minted = await NullAccessTokenRepository().get_new_token(client_entity(), ())

    assert minted.get_user_identifier() is None


async def test_an_empty_resource_owner_is_as_good_as_none() -> None:
    minted = await NullAccessTokenRepository().get_new_token(client_entity(), (), "")

    assert minted.get_user_identifier() is None


async def test_storing_a_token_does_nothing_and_raises_nothing() -> None:
    await NullAccessTokenRepository().persist_new_access_token(access_token_entity())


async def test_withdrawing_a_token_does_nothing_and_raises_nothing() -> None:
    await NullAccessTokenRepository().revoke_access_token("at-1")


async def test_no_token_is_ever_reported_withdrawn() -> None:
    assert await NullAccessTokenRepository().is_access_token_revoked("at-1") is False
