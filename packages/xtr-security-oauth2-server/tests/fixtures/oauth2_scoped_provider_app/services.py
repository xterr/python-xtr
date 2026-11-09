"""The user provider this deployment's firewall loads resource owners through, one per request.

:class:`RequestUnit` stands for the session of the request's unit of work, and
the provider takes it the way a repository takes the session it reads
through, so the container builds one provider per request. Every load is
recorded in :data:`LOADS` with the identity of the instance that answered.
"""

from __future__ import annotations

from typing import Final, final

from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_security_core.exception import UserNotFoundError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface

__all__ = ["LOADS", "RequestUnit", "ScopedUserProvider"]

#: Every load, as the identifier asked for and the identity of the provider asked.
LOADS: Final[list[tuple[str, int]]] = []


@final
@as_service(lifetime="scoped")
class RequestUnit:
    """Stands for the session of the request's unit of work: one per request."""

    __slots__ = ()


@final
@as_service(lifetime="scoped")
class ScopedUserProvider(UserProviderInterface):
    """Loads the deployment's one resource owner through the request's unit."""

    __slots__ = ("unit",)

    def __init__(self, unit: RequestUnit) -> None:
        self.unit = unit

    @override
    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        """Return the resource owner ``identifier`` names.

        Raises:
            UserNotFoundError: For anyone but ``ada``.
        """
        LOADS.append((identifier, id(self)))
        if identifier != "ada":
            raise UserNotFoundError(user_identifier=identifier)
        return InMemoryUser(identifier, roles=["ROLE_USER"])

    @override
    async def refresh_user(self, user: UserInterface) -> UserInterface:
        """Return ``user`` unchanged: the deployment keeps no session."""
        return user

    @override
    def supports_class(self, user_class: type) -> bool:
        """Support the in-memory user this provider builds."""
        return issubclass(user_class, InMemoryUser)
