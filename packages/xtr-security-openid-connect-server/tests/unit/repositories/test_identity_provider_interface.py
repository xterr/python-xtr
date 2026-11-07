"""The identity-provider contract is runtime-checkable, and asks for the user lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_core.exception import UserNotFoundError

from xtr_security_openid_connect_server.repositories.identity_provider_interface import (
    IdentityProviderInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )

    from xtr_security_openid_connect_server.entities.user_claims_entity_interface import (
        UserClaimsEntityInterface,
    )


@final
class _ApplicationIdentityProvider:
    # An application's own class, sharing no base with the contract. It knows
    # nobody, which is all a test of the contract's shape needs.
    async def get_user_entity_by_identifier(
        self,
        identifier: str,
        client: ClientEntityInterface,
    ) -> UserClaimsEntityInterface:
        del client
        raise UserNotFoundError(identifier)


@final
class _Nothing:
    """A class that looks nobody up."""


def test_a_class_with_the_lookup_satisfies_the_contract() -> None:
    provider: IdentityProviderInterface = _ApplicationIdentityProvider()

    assert isinstance(provider, IdentityProviderInterface)


def test_a_class_without_it_does_not_satisfy_it() -> None:
    assert not isinstance(_Nothing(), IdentityProviderInterface)
