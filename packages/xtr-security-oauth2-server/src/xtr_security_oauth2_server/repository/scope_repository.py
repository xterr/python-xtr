"""Which scope names this server knows, and what a token is finally granted."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- container hydrates this constructor at runtime
    EventDispatcherInterface,
)

from xtr_security_oauth2_server.converter.scope_converter_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ScopeConverterInterface,
)
from xtr_security_oauth2_server.event.scope_resolve_event import ScopeResolveEvent
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ClientManagerInterface,
)
from xtr_security_oauth2_server.manager.scope_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ScopeManagerInterface,
)
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.repositories.scope_repository_interface import (
    ScopeRepositoryInterface,
)
from xtr_security_oauth2_server.value_object.grant import Grant

from ._stored_client import stored_client_of

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface
    from xtr_security_oauth2_server.model.client_interface import ClientInterface
    from xtr_security_oauth2_server.value_object.scope import Scope

__all__ = ["ScopeRepository"]


@final
class ScopeRepository(ScopeRepositoryInterface):
    """Looks a scope name up, and settles the set a token is granted.

    The two halves answer different questions. Looking a name up asks whether
    this deployment knows it at all, and an unknown name makes the request
    invalid. Settling asks what the client, the grant and the resource owner
    actually get — and the answer is the last word, because it is what gets
    written into the token.

    Settling happens in two steps, in this order. First the client's own
    registration narrows the set, which is a rule nobody can opt out of: a
    client registered for certain scopes cannot be granted another, and one
    registered for none is granted whatever it asked for. Only then is the
    application asked, so a listener widening a set is widening something the
    registration already allowed.
    """

    def __init__(
        self,
        scope_manager: ScopeManagerInterface,
        client_manager: ClientManagerInterface,
        scope_converter: ScopeConverterInterface,
        dispatcher: EventDispatcherInterface,
    ) -> None:
        """Read scopes and clients from the managers, ask the application through ``dispatcher``."""
        self._scope_manager = scope_manager
        self._client_manager = client_manager
        self._scope_converter = scope_converter
        self._dispatcher = dispatcher

    @override
    def __repr__(self) -> str:
        """Name the type; the collaborators say nothing a reader needs."""
        return f"{type(self).__name__}()"

    @override
    async def get_scope_entity_by_identifier(
        self,
        identifier: str,
    ) -> ScopeEntityInterface | None:
        """Return the scope named ``identifier``, or ``None`` when unknown."""
        scope = await self._scope_manager.find(identifier)
        if scope is None:
            return None

        return self._scope_converter.to_entity(scope)

    @override
    async def finalize_scopes(
        self,
        scopes: Sequence[ScopeEntityInterface],
        grant_type: str,
        client_entity: ClientEntityInterface,
        user_identifier: str | None = None,
        auth_code_id: str | None = None,
    ) -> Sequence[ScopeEntityInterface]:
        """Return the scopes actually granted, from the ones requested.

        ``auth_code_id`` is carried for the contract's sake and read by
        nobody here: narrowing a refresh or an exchange to what was consented
        to when the code was issued is a deployment's rule, and it reads the
        code itself.

        Raises:
            OAuthServerError: ``invalid_scope``, when the client asked for a
                scope its registration does not allow.
        """
        del auth_code_id
        client = await stored_client_of(self._client_manager, client_entity)
        narrowed = _narrowed_to_registration(
            client,
            self._scope_converter.to_domain_sequence(scopes),
        )
        event = await self._dispatcher.dispatch(
            ScopeResolveEvent(narrowed, Grant(grant_type), client, user_identifier),
            OAuth2Events.SCOPE_RESOLVE,
        )

        return self._scope_converter.to_entity_sequence(event.get_scopes())


def _narrowed_to_registration(
    client: ClientInterface,
    requested: Sequence[Scope],
) -> Sequence[Scope]:
    """Return the requested scopes the client's registration allows.

    Raises:
        OAuthServerError: ``invalid_scope``, naming the first scope the
            client's registration does not allow.
    """
    allowed = client.get_scopes()
    if not allowed:
        return requested
    if not requested:
        return allowed

    allowed_names = {str(scope) for scope in allowed}
    for scope in requested:
        if str(scope) not in allowed_names:
            raise OAuthServerError.invalid_scope(str(scope))

    return requested
