"""The described-user contract asks for the identifier and the claims, both."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_oauth2_server.entity import User

from xtr_security_openid_connect_server.entities.user_claims_entity_interface import (
    UserClaimsEntityInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


@final
class _ApplicationUser:
    # An application's own class, sharing no base with the contract.
    def get_identifier(self) -> str:
        return "alice"

    async def get_claims(self) -> Mapping[str, object]:
        return {"name": "Alice"}


@final
class _ClaimsOnly:
    async def get_claims(self) -> Mapping[str, object]:
        return {"name": "Alice"}


def test_a_user_with_an_identifier_and_claims_satisfies_the_contract() -> None:
    user: UserClaimsEntityInterface = _ApplicationUser()

    assert isinstance(user, UserClaimsEntityInterface)


def test_the_authorization_servers_own_user_does_not_satisfy_it() -> None:
    # Named by its identifier alone: nothing on it describes who the user is.
    user = User()
    user.set_identifier("alice")

    assert not isinstance(user, UserClaimsEntityInterface)


def test_claims_naming_nobody_do_not_satisfy_it() -> None:
    assert not isinstance(_ClaimsOnly(), UserClaimsEntityInterface)
