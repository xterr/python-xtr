"""An identity provider holding one user, for the tests to describe.

The served tests sign in as alice and read her claims back, so this holds
exactly her: the name ``Alice`` and a verified ``alice@example.com``. It is a
fake, not a mock — it really answers from the users it holds — and
``test_identity_provider.py`` beside it proves it keeps the contract it stands
in for, the error for an identifier it does not hold included.

It builds with no arguments, so a fixture application can name the class as
its identity provider and let the container build it.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, final

from xtr_security_core.exception import UserNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )

    from xtr_security_openid_connect_server.entities.user_claims_entity_interface import (
        UserClaimsEntityInterface,
    )

__all__ = ["ClaimsUser", "InMemoryIdentityProvider"]


@final
class ClaimsUser:
    """A resource owner named by its identifier, holding the claims it was given."""

    __slots__ = ("_claims", "_identifier")

    def __init__(self, identifier: str, claims: Mapping[str, object]) -> None:
        self._identifier = identifier
        # A copy behind a read-only view: whoever reads the claims cannot
        # change what the next reading answers.
        self._claims: Mapping[str, object] = MappingProxyType(dict(claims))

    def get_identifier(self) -> str:
        return self._identifier

    async def get_claims(self) -> Mapping[str, object]:
        return self._claims


@final
class InMemoryIdentityProvider:
    """Answers alice's identifier with alice, and any other with the contract's error."""

    __slots__ = ("_users",)

    def __init__(self) -> None:
        alice = ClaimsUser(
            "alice",
            {"name": "Alice", "email": "alice@example.com", "email_verified": True},
        )
        self._users: dict[str, ClaimsUser] = {alice.get_identifier(): alice}

    async def get_user_entity_by_identifier(
        self,
        identifier: str,
        client: ClientEntityInterface,
    ) -> UserClaimsEntityInterface:
        del client  # Every client is told the same about a user here.
        user = self._users.get(identifier)
        if user is None:
            raise UserNotFoundError(identifier)
        return user
