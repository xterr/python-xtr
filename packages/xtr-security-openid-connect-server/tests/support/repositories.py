"""In-memory storage an authorization server built by hand runs against.

These are fakes, not mocks: they really store what they are handed and really
answer from what they stored, so a test of a whole code flow asserts on what the
server answered rather than on calls being made. The entities they mint are the
ones the authorization server package ships, so a token signs itself exactly as
a deployment's does. ``test_repositories.py`` beside this proves each keeps the
contract it stands in for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_oauth2_server.entity import AccessToken, AuthCode, RefreshToken, Scope

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.auth_code_entity_interface import (
        AuthCodeEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.scope_entity_interface import ScopeEntityInterface

__all__ = [
    "InMemoryAccessTokenRepository",
    "InMemoryAuthCodeRepository",
    "InMemoryClientRepository",
    "InMemoryRefreshTokenRepository",
    "InMemoryScopeRepository",
]


@final
class InMemoryClientRepository:
    """Holds registered clients and the secrets the confidential ones prove."""

    def __init__(self) -> None:
        self.clients: dict[str, ClientEntityInterface] = {}
        self.secrets: dict[str, str] = {}

    def add(self, client: ClientEntityInterface, secret: str | None = None) -> None:
        """Register ``client``, with ``secret`` when it is confidential."""
        self.clients[client.get_identifier()] = client
        if secret is not None:
            self.secrets[client.get_identifier()] = secret

    async def get_client_entity(self, client_identifier: str) -> ClientEntityInterface | None:
        return self.clients.get(client_identifier)

    async def validate_client(
        self,
        client_identifier: str,
        client_secret: str | None,
        grant_type: str | None,
    ) -> bool:
        del grant_type  # Every client here may use every grant.
        return self.secrets.get(client_identifier) == client_secret


@final
class InMemoryAccessTokenRepository:
    """Mints and stores access tokens, and remembers which were revoked."""

    def __init__(self) -> None:
        self.tokens: dict[str, AccessTokenEntityInterface] = {}
        self.revoked: set[str] = set()

    async def get_new_token(
        self,
        client_entity: ClientEntityInterface,
        scopes: Sequence[ScopeEntityInterface],
        user_identifier: str | None = None,
    ) -> AccessTokenEntityInterface:
        token = AccessToken()
        token.set_client(client_entity)
        for scope in scopes:
            token.add_scope(scope)
        if user_identifier is not None:
            token.set_user_identifier(user_identifier)
        return token

    async def persist_new_access_token(
        self,
        access_token_entity: AccessTokenEntityInterface,
    ) -> None:
        self.tokens[access_token_entity.get_identifier()] = access_token_entity

    async def revoke_access_token(self, token_id: str) -> None:
        self.revoked.add(token_id)

    async def is_access_token_revoked(self, token_id: str) -> bool:
        return token_id in self.revoked


@final
class InMemoryAuthCodeRepository:
    """Mints and stores authorization codes, and remembers which were redeemed."""

    def __init__(self) -> None:
        self.codes: dict[str, AuthCodeEntityInterface] = {}
        self.revoked: set[str] = set()

    async def get_new_auth_code(self) -> AuthCodeEntityInterface:
        return AuthCode()

    async def persist_new_auth_code(self, auth_code_entity: AuthCodeEntityInterface) -> None:
        self.codes[auth_code_entity.get_identifier()] = auth_code_entity

    async def revoke_auth_code(self, code_id: str) -> None:
        self.revoked.add(code_id)

    async def is_auth_code_revoked(self, code_id: str) -> bool:
        return code_id in self.revoked


@final
class InMemoryRefreshTokenRepository:
    """Mints and stores refresh tokens, revoking by check-and-set."""

    def __init__(self) -> None:
        self.tokens: dict[str, RefreshTokenEntityInterface] = {}
        self.revoked: set[str] = set()

    async def get_new_refresh_token(self) -> RefreshTokenEntityInterface | None:
        return RefreshToken()

    async def persist_new_refresh_token(
        self,
        refresh_token_entity: RefreshTokenEntityInterface,
    ) -> None:
        self.tokens[refresh_token_entity.get_identifier()] = refresh_token_entity

    async def revoke_refresh_token(self, token_id: str) -> bool:
        if token_id in self.revoked:
            return False
        self.revoked.add(token_id)
        return True

    async def is_refresh_token_revoked(self, token_id: str) -> bool:
        return token_id in self.revoked


@final
class InMemoryScopeRepository:
    """Knows a fixed set of scopes, and grants every one a request asks for."""

    def __init__(self, *identifiers: str) -> None:
        self.scopes: dict[str, ScopeEntityInterface] = {}
        for identifier in identifiers:
            scope = Scope()
            scope.set_identifier(identifier)
            self.scopes[identifier] = scope

    async def get_scope_entity_by_identifier(
        self,
        identifier: str,
    ) -> ScopeEntityInterface | None:
        return self.scopes.get(identifier)

    async def finalize_scopes(
        self,
        scopes: Sequence[ScopeEntityInterface],
        grant_type: str,
        client_entity: ClientEntityInterface,
        user_identifier: str | None = None,
        auth_code_id: str | None = None,
    ) -> Sequence[ScopeEntityInterface]:
        del grant_type, client_entity, user_identifier, auth_code_id  # Granted as asked.
        return tuple(scopes)
