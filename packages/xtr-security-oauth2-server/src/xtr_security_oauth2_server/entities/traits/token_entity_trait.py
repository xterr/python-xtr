"""The state every issued token holds: the client, the window, the scopes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface

__all__ = ["TokenEntityTrait"]


class TokenEntityTrait:
    """Holds what a token is for: a client, a resource owner, scopes, an expiry.

    Compose it with the identifier trait and the trait of the particular token
    — access token, authorization code, device code — and the entity is done.

    The scopes are kept keyed by identifier, so adding the same scope twice
    carries it once: the grants build a token's scopes from a request and then
    from whatever the scope repository finalised, and a scope arriving by both
    routes must not be written into the token twice. The place a scope first
    took is the place it keeps, so the order a token reports is the order it was
    granted in — which is the order the ``scope`` claim and the token response
    read out.
    """

    _client: ClientEntityInterface
    _expiry_date_time: datetime
    _user_identifier: str | None = None

    #: Keyed by identifier, so the same scope cannot be carried twice; the
    #: insertion order of the mapping is the order the token reports.
    _scopes: dict[str, ScopeEntityInterface]

    def get_expiry_date_time(self) -> datetime:
        """Return the instant this token stops being accepted."""
        return self._expiry_date_time

    def set_expiry_date_time(self, date_time: datetime) -> None:
        """Stop accepting this token at ``date_time``, which must be aware."""
        self._expiry_date_time = date_time

    def get_user_identifier(self) -> str | None:
        """Return the resource owner this token is for, or ``None`` for none."""
        return self._user_identifier

    def set_user_identifier(self, identifier: str) -> None:
        """Issue this token on behalf of the resource owner ``identifier``."""
        self._user_identifier = identifier

    def get_client(self) -> ClientEntityInterface:
        """Return the client this token was issued to."""
        return self._client

    def set_client(self, client: ClientEntityInterface) -> None:
        """Issue this token to ``client``."""
        self._client = client

    def get_scopes(self) -> Sequence[ScopeEntityInterface]:
        """Return the scopes this token carries, in the order they were added."""
        return tuple(self._scopes_held().values())

    def add_scope(self, scope: ScopeEntityInterface) -> None:
        """Let this token carry ``scope``, once however often it is added."""
        self._scopes_held()[scope.get_identifier()] = scope

    def _scopes_held(self) -> dict[str, ScopeEntityInterface]:
        """Return the mapping the scopes live in, starting it on first use.

        A trait cannot run a constructor — an entity composing several of them
        would have to call each one — so the mapping appears the first time a
        scope is added or read.
        """
        try:
            return self._scopes
        except AttributeError:
            self._scopes = {}
            return self._scopes
