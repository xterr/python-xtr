"""In-memory storage the grant tests run against, one fake per storage contract.

These are fakes, not mocks: they really store what they are handed and really
answer from what they stored, so a test asserts on the state a grant left
behind rather than on a call being made. Each one satisfies the contract it
stands for, and ``test_repositories.py`` holds the contract tests proving it.

Two knobs exist only because a grant's behaviour depends on them and nothing
else can produce them: ``collisions``, which makes the next few stores report a
taken identifier so the retry loop can be exercised, and the refresh-token
repository's ``issues`` flag, which is how a deployment opts out of refresh
tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_security_oauth2_server_core.exception import UniqueTokenIdentifierConstraintViolationError

from tests.support.entities import AccessToken, AuthCode, DeviceCode, RefreshToken, make_scope

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server_core.entities import ClientEntityInterface
    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.auth_code_entity_interface import (
        AuthCodeEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.device_code_entity_interface import (
        DeviceCodeEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.scope_entity_interface import ScopeEntityInterface
    from xtr_security_oauth2_server_core.entities.user_entity_interface import UserEntityInterface

__all__ = [
    "CredentialsAsked",
    "FinalizeCall",
    "InMemoryAccessTokenRepository",
    "InMemoryAuthCodeRepository",
    "InMemoryClientRepository",
    "InMemoryDeviceCodeRepository",
    "InMemoryRefreshTokenRepository",
    "InMemoryScopeRepository",
    "InMemoryUserRepository",
]


@final
@dataclass(frozen=True, slots=True)
class FinalizeCall:
    """One call to ``finalize_scopes``, exactly as the grant made it."""

    scopes: Sequence[ScopeEntityInterface]
    grant_type: str
    client_entity: ClientEntityInterface
    user_identifier: str | None
    auth_code_id: str | None


@dataclass(slots=True)
class _Collisions:
    """How many more stores report that the identifier was already taken."""

    remaining: int = 0

    def claim(self) -> None:
        """Report a taken identifier, while any collision is still owed."""
        if self.remaining > 0:
            self.remaining -= 1
            raise UniqueTokenIdentifierConstraintViolationError.create()


@final
class InMemoryClientRepository:
    """Holds registered clients and the secrets they authenticate with."""

    def __init__(self) -> None:
        self.clients: dict[str, ClientEntityInterface] = {}
        self.secrets: dict[str, str] = {}
        self.allowed_grants: dict[str, tuple[str, ...]] = {}

    def add(
        self,
        client: ClientEntityInterface,
        secret: str | None = None,
        grant_types: Sequence[str] | None = None,
    ) -> None:
        """Register ``client``, with ``secret`` when it is confidential."""
        identifier = client.get_identifier()
        self.clients[identifier] = client
        if secret is not None:
            self.secrets[identifier] = secret
        if grant_types is not None:
            self.allowed_grants[identifier] = tuple(grant_types)

    async def get_client_entity(self, client_identifier: str) -> ClientEntityInterface | None:
        """Return the client registered as ``client_identifier``, or ``None``."""
        return self.clients.get(client_identifier)

    async def validate_client(
        self,
        client_identifier: str,
        client_secret: str | None,
        grant_type: str | None,
    ) -> bool:
        """Tell whether the secret matches and the grant is one this client may use."""
        allowed = self.allowed_grants.get(client_identifier)
        if allowed is not None and grant_type is not None and grant_type not in allowed:
            return False

        return self.secrets.get(client_identifier) == client_secret


@final
class InMemoryAccessTokenRepository:
    """Mints and stores access tokens, and remembers which were revoked."""

    def __init__(self) -> None:
        self.tokens: dict[str, AccessTokenEntityInterface] = {}
        self.revoked: set[str] = set()
        self.collisions: _Collisions = _Collisions()

    async def get_new_token(
        self,
        client_entity: ClientEntityInterface,
        scopes: Sequence[ScopeEntityInterface],
        user_identifier: str | None = None,
    ) -> AccessTokenEntityInterface:
        """Return a new, unstored token already carrying its client and scopes."""
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
        """Store ``access_token_entity`` under the identifier it carries."""
        self.collisions.claim()
        self.tokens[access_token_entity.get_identifier()] = access_token_entity

    async def revoke_access_token(self, token_id: str) -> None:
        """Stop accepting the access token named ``token_id``."""
        self.revoked.add(token_id)

    async def is_access_token_revoked(self, token_id: str) -> bool:
        """Tell whether the access token named ``token_id`` was revoked."""
        return token_id in self.revoked


@final
class InMemoryAuthCodeRepository:
    """Mints and stores authorization codes, and remembers which were redeemed."""

    def __init__(self) -> None:
        self.codes: dict[str, AuthCodeEntityInterface] = {}
        self.revoked: set[str] = set()
        self.collisions: _Collisions = _Collisions()

    async def get_new_auth_code(self) -> AuthCodeEntityInterface:
        """Return a new, unstored authorization code."""
        return AuthCode()

    async def persist_new_auth_code(self, auth_code_entity: AuthCodeEntityInterface) -> None:
        """Store ``auth_code_entity`` under the identifier it carries."""
        self.collisions.claim()
        self.codes[auth_code_entity.get_identifier()] = auth_code_entity

    async def revoke_auth_code(self, code_id: str) -> None:
        """Stop accepting the authorization code named ``code_id``."""
        self.revoked.add(code_id)

    async def is_auth_code_revoked(self, code_id: str) -> bool:
        """Tell whether the authorization code named ``code_id`` was revoked."""
        return code_id in self.revoked


@final
class InMemoryRefreshTokenRepository:
    """Mints and stores refresh tokens, revoking by check-and-set."""

    def __init__(self, *, issues: bool = True) -> None:
        """Hold nothing yet; ``issues=False`` opts this deployment out of refresh tokens."""
        self.tokens: dict[str, RefreshTokenEntityInterface] = {}
        self.revoked: set[str] = set()
        self.collisions: _Collisions = _Collisions()
        self.issues: bool = issues

    async def get_new_refresh_token(self) -> RefreshTokenEntityInterface | None:
        """Return a new, unstored refresh token, or ``None`` to issue none."""
        return RefreshToken() if self.issues else None

    async def persist_new_refresh_token(
        self,
        refresh_token_entity: RefreshTokenEntityInterface,
    ) -> None:
        """Store ``refresh_token_entity`` under the identifier it carries."""
        self.collisions.claim()
        self.tokens[refresh_token_entity.get_identifier()] = refresh_token_entity

    async def revoke_refresh_token(self, token_id: str) -> bool:
        """Revoke ``token_id``, reporting whether this call is what revoked it."""
        if token_id in self.revoked:
            return False
        self.revoked.add(token_id)

        return True

    async def is_refresh_token_revoked(self, token_id: str) -> bool:
        """Tell whether the refresh token named ``token_id`` was revoked."""
        return token_id in self.revoked


@final
class InMemoryScopeRepository:
    """Knows a fixed set of scopes, and records every set it was asked to finalise."""

    def __init__(self, *identifiers: str) -> None:
        """Know one scope per identifier given."""
        self.scopes: dict[str, ScopeEntityInterface] = {
            identifier: make_scope(identifier) for identifier in identifiers
        }
        self.finalized: list[FinalizeCall] = []
        self.grants: Sequence[ScopeEntityInterface] | None = None

    async def get_scope_entity_by_identifier(
        self,
        identifier: str,
    ) -> ScopeEntityInterface | None:
        """Return the scope named ``identifier``, or ``None`` when unknown."""
        return self.scopes.get(identifier)

    async def finalize_scopes(
        self,
        scopes: Sequence[ScopeEntityInterface],
        grant_type: str,
        client_entity: ClientEntityInterface,
        user_identifier: str | None = None,
        auth_code_id: str | None = None,
    ) -> Sequence[ScopeEntityInterface]:
        """Record the call and answer the scopes asked for, or the override set."""
        self.finalized.append(
            FinalizeCall(tuple(scopes), grant_type, client_entity, user_identifier, auth_code_id),
        )

        return tuple(scopes) if self.grants is None else self.grants


@final
@dataclass(frozen=True, slots=True)
class CredentialsAsked:
    """One call to ``get_user_entity_by_user_credentials``, as the grant made it."""

    username: str
    password: str
    grant_type: str
    client_identifier: str


@final
class InMemoryUserRepository:
    """Answers a username and password with the resource owner they belong to."""

    def __init__(self) -> None:
        self.users: dict[tuple[str, str], UserEntityInterface] = {}
        self.asked: list[CredentialsAsked] = []

    def add(self, username: str, password: str, user: UserEntityInterface) -> None:
        """Let ``username`` and ``password`` identify ``user``."""
        self.users[username, password] = user

    async def get_user_entity_by_user_credentials(
        self,
        username: str,
        password: str,
        grant_type: str,
        client_entity: ClientEntityInterface,
    ) -> UserEntityInterface | None:
        """Return the resource owner the credentials belong to, or ``None``."""
        self.asked.append(
            CredentialsAsked(username, password, grant_type, client_entity.get_identifier()),
        )

        return self.users.get((username, password))


@final
class InMemoryDeviceCodeRepository:
    """Mints, stores, finds and revokes device codes."""

    def __init__(self) -> None:
        self.codes: dict[str, DeviceCodeEntityInterface] = {}
        self.revoked: set[str] = set()
        self.collisions: _Collisions = _Collisions()

    async def get_new_device_code(self) -> DeviceCodeEntityInterface:
        """Return a new, unstored device code."""
        return DeviceCode()

    async def persist_device_code(self, device_code_entity: DeviceCodeEntityInterface) -> None:
        """Store ``device_code_entity``, new or already known."""
        self.collisions.claim()
        self.codes[device_code_entity.get_identifier()] = device_code_entity

    async def get_device_code_entity_by_device_code(
        self,
        device_code: str,
    ) -> DeviceCodeEntityInterface | None:
        """Return the stored code named ``device_code``, or ``None``."""
        return self.codes.get(device_code)

    async def revoke_device_code(self, code_id: str) -> None:
        """Stop accepting the device code named ``code_id``."""
        self.revoked.add(code_id)

    async def is_device_code_revoked(self, code_id: str) -> bool:
        """Tell whether the device code named ``code_id`` was revoked."""
        return code_id in self.revoked
