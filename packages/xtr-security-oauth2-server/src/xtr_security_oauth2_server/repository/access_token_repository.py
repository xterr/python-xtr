"""Minting an access token, writing it down, and withdrawing it again."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- container hydrates this constructor at runtime
    EventDispatcherInterface,
)

from xtr_security_oauth2_server.converter.scope_converter_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ScopeConverterInterface,
)
from xtr_security_oauth2_server.entity.access_token import AccessToken as AccessTokenEntity
from xtr_security_oauth2_server.event.access_token_extra_claims_resolve_event import (
    AccessTokenExtraClaimsResolveEvent,
)
from xtr_security_oauth2_server.exception import (
    UniqueTokenIdentifierConstraintViolationError,
)
from xtr_security_oauth2_server.manager.access_token_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ClientManagerInterface,
)
from xtr_security_oauth2_server.model.access_token import AccessToken as AccessTokenModel
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)

from ._stored_client import stored_client_of

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface

__all__ = ["AccessTokenRepository"]


@final
class AccessTokenRepository(AccessTokenRepositoryInterface):
    """Mints the access-token entity, stores what was issued, and revokes it.

    Minting is where the application gets its claims in, and it has to be
    *before* the entity exists in any usable form: the claims are signed into
    the token, so asking afterwards would mean either signing twice or
    handing out something nobody verified.

    Storing refuses an identifier already taken rather than overwriting it.
    Two tokens under one name would make revoking one revoke the other, and
    the grant that hit the collision simply mints another identifier and tries
    again.
    """

    def __init__(
        self,
        access_token_manager: AccessTokenManagerInterface,
        client_manager: ClientManagerInterface,
        scope_converter: ScopeConverterInterface,
        dispatcher: EventDispatcherInterface,
    ) -> None:
        """Store tokens through the managers, ask for claims through ``dispatcher``."""
        self._access_token_manager = access_token_manager
        self._client_manager = client_manager
        self._scope_converter = scope_converter
        self._dispatcher = dispatcher

    @override
    def __repr__(self) -> str:
        """Name the type; the collaborators say nothing a reader needs."""
        return f"{type(self).__name__}()"

    @override
    async def get_new_token(
        self,
        client_entity: ClientEntityInterface,
        scopes: Sequence[ScopeEntityInterface],
        user_identifier: str | None = None,
    ) -> AccessTokenEntityInterface:
        """Return a new, unstored token for ``client_entity`` and ``scopes``.

        Raises:
            InvalidArgumentError: When a listener asked for a claim the token
                mints itself. The entity refuses it, naming the claim, rather
                than letting a listener quietly reissue the issuer or the
                expiry.
        """
        event = await self._dispatcher.dispatch(
            AccessTokenExtraClaimsResolveEvent(client_entity, scopes, user_identifier),
            OAuth2Events.ACCESS_TOKEN_EXTRA_CLAIMS_RESOLVE,
        )

        token = AccessTokenEntity()
        token.set_client(client_entity)
        if user_identifier:
            token.set_user_identifier(user_identifier)
        for scope in scopes:
            token.add_scope(scope)
        extra_claims = event.get_extra_claims()
        if extra_claims:
            token.set_extra_claims(extra_claims)

        return token

    @override
    async def persist_new_access_token(
        self,
        access_token_entity: AccessTokenEntityInterface,
    ) -> None:
        """Store ``access_token_entity``.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When a token of
                that identifier is already stored.
            InvalidArgumentError: When no client is stored under the
                identifier the token names.
        """
        identifier = access_token_entity.get_identifier()
        if await self._access_token_manager.find(identifier) is not None:
            raise UniqueTokenIdentifierConstraintViolationError.create()

        client = await stored_client_of(self._client_manager, access_token_entity.get_client())
        await self._access_token_manager.save(
            AccessTokenModel(
                identifier,
                access_token_entity.get_expiry_date_time(),
                client,
                access_token_entity.get_user_identifier(),
                self._scope_converter.to_domain_sequence(access_token_entity.get_scopes()),
            ),
        )

    @override
    async def revoke_access_token(self, token_id: str) -> None:
        """Stop accepting the access token named ``token_id``."""
        token = await self._access_token_manager.find(token_id)
        if token is None:
            return

        await self._access_token_manager.save(token.revoke())

    @override
    async def is_access_token_revoked(self, token_id: str) -> bool:
        """Tell whether the access token named ``token_id`` was revoked.

        A token nobody stored counts as revoked. A deployment that keeps its
        access tokens has one row per token issued, so a token with no row is
        a token this server did not issue — or one already swept — and either
        way it must not be accepted.
        """
        token = await self._access_token_manager.find(token_id)
        if token is None:
            return True

        return token.is_revoked()
