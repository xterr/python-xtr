"""An access token is about to be minted, and may carry claims of its own."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Self

from typing_extensions import override
from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface

__all__ = ["AccessTokenExtraClaimsResolveEvent"]


class AccessTokenExtraClaimsResolveEvent(Event):
    """Asks what else the access token about to be minted should say.

    Announced before the token exists, so whatever a listener asks for is
    signed into it rather than bolted on afterwards — which is the only way a
    resource server could trust it.

    The claims a token mints itself are refused, but not here: they are
    refused when they are put on the entity, because that is where the rule
    belongs and where an application bringing its own access-token entity
    still has to honour it. A listener therefore learns about a reserved name
    from the error the request fails with, naming the claim.
    """

    def __init__(
        self,
        client_entity: ClientEntityInterface,
        scopes: Sequence[ScopeEntityInterface],
        user_identifier: str | None = None,
    ) -> None:
        """Announce a token about to be minted for ``client_entity``."""
        self._client_entity: ClientEntityInterface = client_entity
        self._scopes: tuple[ScopeEntityInterface, ...] = tuple(scopes)
        self._user_identifier: str | None = user_identifier
        self._extra_claims: Mapping[str, object] = MappingProxyType({})

    def get_client(self) -> ClientEntityInterface:
        """Return the client the token is for."""
        return self._client_entity

    def get_scopes(self) -> Sequence[ScopeEntityInterface]:
        """Return the scopes the token was granted."""
        return self._scopes

    def get_user_identifier(self) -> str | None:
        """Return the resource owner the token acts for, or ``None`` for none."""
        return self._user_identifier

    def set_extra_claims(self, extra_claims: Mapping[str, object]) -> Self:
        """Carry ``extra_claims`` in the token, besides the ones it mints.

        Copied behind a read-only view, so a listener that goes on to change
        its own mapping does not change what the token will say.
        """
        self._extra_claims = MappingProxyType(dict(extra_claims))

        return self

    def get_extra_claims(self) -> Mapping[str, object]:
        """Return the claims asked for, as a read-only view."""
        return self._extra_claims

    @override
    def __repr__(self) -> str:
        """Name the client and which claims were asked for, never their values.

        A claim value is whatever an application put there — a tenant, an
        entitlement, an internal identifier — and none of it belongs in a log
        line. The names do: they are what a reader needs to tell which
        listener ran.
        """
        return (
            f"{type(self).__name__}(client={self._client_entity!r}, "
            f"extra_claims={tuple(self._extra_claims)!r})"
        )
