"""The services the fixture deployment registers: its session backend, and a unit of the request.

The session storage is the application's to register — the security bundle
never builds one on its behalf, since a session kept in one process's memory is
lost to every other. The deployment that signs the end-user in with a form keeps
the login there; the others never open a session, so it stays unused for them.

:class:`RequestUnit` stands for the session of the request's unit of work, one
per request; :class:`ScopedIdentityProvider` takes it, the way a repository
takes the session it reads through, so the deployment naming it proves the
identity provider is built per request. Each unit records its identity in
:data:`REQUEST_UNITS`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_dependency_injection import as_service
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface

from tests.support.identity_provider import InMemoryIdentityProvider

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )

    from xtr_security_openid_connect_server.entities.user_claims_entity_interface import (
        UserClaimsEntityInterface,
    )

__all__ = [
    "REQUEST_UNITS",
    "RequestUnit",
    "ScopedIdentityProvider",
    "fixture_session_storage",
]

#: The identity of every unit built, in the order the requests built them.
REQUEST_UNITS: list[int] = []


@as_service
def fixture_session_storage() -> SessionStorageInterface:
    """The deployment's session storage: in-memory, as a test's own backend."""
    return MemorySessionStorage()


@final
@as_service(lifetime="scoped")
class RequestUnit:
    """Stands for the session of the request's unit of work: one per request."""

    __slots__ = ()

    def __init__(self) -> None:
        REQUEST_UNITS.append(id(self))


@final
class ScopedIdentityProvider:
    """Answers as the in-memory provider does, over the unit of the request it is built in."""

    __slots__ = ("_users", "unit")

    def __init__(self, unit: RequestUnit) -> None:
        self.unit = unit
        self._users = InMemoryIdentityProvider()

    async def get_user_entity_by_identifier(
        self,
        identifier: str,
        client: ClientEntityInterface,
    ) -> UserClaimsEntityInterface:
        """Answer what the in-memory provider answers."""
        return await self._users.get_user_entity_by_identifier(identifier, client)
