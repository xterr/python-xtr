"""Building the consent event out of a request, a stored client and a user."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.converter.scope_converter_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ScopeConverterInterface,
)
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ClientManagerInterface,
)

from .authorization_request_resolve_event import AuthorizationRequestResolveEvent

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_oauth2_server.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )

__all__ = ["AuthorizationRequestResolveEventFactory"]


@final
class AuthorizationRequestResolveEventFactory:
    """Turns a validated authorization request into the event listeners answer.

    Two things the request does not carry have to be found first: the client
    as it is *stored*, so a listener can read the registration a protocol
    entity knows nothing about, and the scopes as stored values rather than
    entities.

    The resource owner is handed in rather than looked up. Reading the user
    belongs to whoever is holding the request — the controller, which has the
    firewall's answer for this very request — and doing it here would tie this
    module to the security bundle and make the event impossible to build in a
    test or from a command.
    """

    __slots__ = ("_client_manager", "_scope_converter")

    def __init__(
        self,
        scope_converter: ScopeConverterInterface,
        client_manager: ClientManagerInterface,
    ) -> None:
        """Convert scopes with ``scope_converter``, find clients in ``client_manager``."""
        self._scope_converter = scope_converter
        self._client_manager = client_manager

    @override
    def __repr__(self) -> str:
        """Name the type; the collaborators say nothing a reader needs."""
        return f"{type(self).__name__}()"

    async def from_authorization_request(
        self,
        authorization_request: AuthorizationRequestInterface,
        user: UserInterface,
    ) -> AuthorizationRequestResolveEvent:
        """Return the event for ``authorization_request``, shown to ``user``.

        Raises:
            InvalidArgumentError: When no client is stored under the
                identifier the request names. The request was validated
                against a client entity, so finding none here means the two
                sides disagree — a client removed mid-flow, or a repository
                and a manager pointed at different stores — and answering a
                protocol error would hide a broken deployment.
        """
        identifier = authorization_request.get_client().get_identifier()
        client = await self._client_manager.find(identifier)
        if client is None:
            raise InvalidArgumentError(
                f"No client is stored under the identifier {identifier!r}, although an "
                "authorization request was validated against one; the client repository "
                "and the client manager are reading different stores.",
            )

        return AuthorizationRequestResolveEvent(
            authorization_request,
            self._scope_converter.to_domain_sequence(authorization_request.get_scopes()),
            client,
            user,
        )
