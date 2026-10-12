"""Withdrawing everything a user or a client holds, in one call."""

from __future__ import annotations

from typing import final

import pytest

from tests.support.models import client_model
from tests.support.users import SecurityUser
from xtr_security_oauth2_server.model.client_interface import ClientInterface
from xtr_security_oauth2_server.service.credentials_revoker_interface import (
    CredentialsRevokerInterface,
)

pytestmark = pytest.mark.anyio


@final
class _Revoker:
    """Records who was asked about, the way a stored one would write the rows."""

    def __init__(self) -> None:
        self.users: list[str] = []
        self.clients: list[str] = []

    async def revoke_credentials_for_user(self, user: SecurityUser) -> None:
        self.users.append(user.get_user_identifier())

    async def revoke_credentials_for_client(self, client: ClientInterface) -> None:
        self.clients.append(client.get_identifier())


def test_an_implementation_satisfies_the_contract() -> None:
    assert isinstance(_Revoker(), CredentialsRevokerInterface)


async def test_it_is_asked_about_a_user_by_the_user() -> None:
    revoker = _Revoker()

    await revoker.revoke_credentials_for_user(SecurityUser("someone"))

    assert revoker.users == ["someone"]


async def test_it_is_asked_about_a_client_by_the_client() -> None:
    revoker = _Revoker()

    await revoker.revoke_credentials_for_client(client_model("client-1"))

    assert revoker.clients == ["client-1"]
