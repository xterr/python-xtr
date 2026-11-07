"""The in-memory identity provider really keeps the contract it stands in for.

A fake is only worth trusting while it behaves like the thing it replaces, so
it is checked against its contract here: it answers the protocol, it finds the
user it holds with the claims the served tests read back, and an identifier it
does not hold raises the error the contract names.
"""

from __future__ import annotations

import pytest
from xtr_security_core.exception import UserNotFoundError
from xtr_security_oauth2_server.entity import Client

from tests.support.identity_provider import InMemoryIdentityProvider
from xtr_security_openid_connect_server.repositories.identity_provider_interface import (
    IdentityProviderInterface,
)

pytestmark = pytest.mark.anyio


def _client() -> Client:
    """Return the client every lookup here is made for."""
    client = Client()
    client.set_identifier("my-client")
    return client


def test_it_satisfies_the_identity_provider_contract() -> None:
    provider: IdentityProviderInterface = InMemoryIdentityProvider()

    assert isinstance(provider, IdentityProviderInterface)


async def test_it_finds_alice_by_her_identifier() -> None:
    user = await InMemoryIdentityProvider().get_user_entity_by_identifier("alice", _client())

    assert user.get_identifier() == "alice"


async def test_alice_holds_her_name_and_her_verified_email() -> None:
    user = await InMemoryIdentityProvider().get_user_entity_by_identifier("alice", _client())

    assert await user.get_claims() == {
        "name": "Alice",
        "email": "alice@example.com",
        "email_verified": True,
    }


async def test_an_identifier_it_does_not_hold_raises_user_not_found() -> None:
    with pytest.raises(UserNotFoundError) as raised:
        _ = await InMemoryIdentityProvider().get_user_entity_by_identifier("bob", _client())

    assert raised.value.user_identifier == "bob"
