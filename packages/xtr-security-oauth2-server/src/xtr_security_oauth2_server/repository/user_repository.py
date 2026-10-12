"""Who the credentials a client sent belong to, asked of the application."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- container hydrates this constructor at runtime
    EventDispatcherInterface,
)

from xtr_security_oauth2_server.converter.user_converter_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    UserConverterInterface,
)
from xtr_security_oauth2_server.event.user_resolve_event import UserResolveEvent
from xtr_security_oauth2_server.manager.client_manager_interface import (
    ClientManagerInterface,
)
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from xtr_security_oauth2_server.value_object.grant import Grant

from ._stored_client import stored_client_of

if TYPE_CHECKING:
    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.user_entity_interface import UserEntityInterface
    from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface

__all__ = ["UserRepository"]


@final
class UserRepository(UserRepositoryInterface):
    """Asks the application whose credentials these are, and narrows the answer.

    This package checks no password. It cannot: a resource owner's credentials
    belong to the application's own user store, and the one flow that sends
    them is the one flow a deployment has to answer for itself. So the
    question goes out as an event, and what comes back is narrowed to the
    identifier a token carries.

    Nobody answering means the request is refused — which is also the answer
    for a wrong password, a user that does not exist, and an account this
    client may not act for, because telling the three apart is how accounts
    get enumerated.
    """

    def __init__(
        self,
        client_manager: ClientManagerInterface,
        dispatcher: EventDispatcherInterface,
        user_converter: UserConverterInterface,
    ) -> None:
        """Read clients from ``client_manager``, ask the application through ``dispatcher``."""
        self._client_manager = client_manager
        self._dispatcher = dispatcher
        self._user_converter = user_converter

    @override
    def __repr__(self) -> str:
        """Name the type; the collaborators say nothing a reader needs."""
        return f"{type(self).__name__}()"

    @override
    async def get_user_entity_by_user_credentials(
        self,
        username: str,
        password: str,
        grant_type: str,
        client_entity: ClientEntityInterface,
    ) -> UserEntityInterface | None:
        """Return the resource owner the credentials belong to, or ``None``.

        The stored client is handed to the listener as well, so a deployment
        can let one client check credentials and refuse another.
        """
        client = await stored_client_of(self._client_manager, client_entity)
        event = await self._dispatcher.dispatch(
            UserResolveEvent(username, password, Grant(grant_type), client),
            OAuth2Events.USER_RESOLVE,
        )
        user = event.get_user()
        if user is None:
            return None

        return self._user_converter.to_entity(user)
