"""The six stores this application registers, each a service the scan finds."""

from __future__ import annotations

from xtr_dependency_injection import as_service

from tests.support.custom_stores import (
    ApplicationAccessTokenStore,
    ApplicationAuthorizationCodeStore,
    ApplicationClientStore,
    ApplicationCredentialsRevoker,
    ApplicationDeviceCodeStore,
    ApplicationRefreshTokenStore,
)

__all__ = [
    "AccessTokenStore",
    "AuthorizationCodeStore",
    "ClientStore",
    "CredentialsRevoker",
    "DeviceCodeStore",
    "RefreshTokenStore",
]


@as_service
class ClientStore(ApplicationClientStore):
    """Where this application keeps its registered clients."""


@as_service
class AccessTokenStore(ApplicationAccessTokenStore):
    """Where this application keeps its issued access tokens."""


@as_service
class AuthorizationCodeStore(ApplicationAuthorizationCodeStore):
    """Where this application keeps its issued authorization codes."""


@as_service
class RefreshTokenStore(ApplicationRefreshTokenStore):
    """Where this application keeps its issued refresh tokens."""


@as_service
class DeviceCodeStore(ApplicationDeviceCodeStore):
    """Where this application keeps its issued device codes."""


@as_service
class CredentialsRevoker(ApplicationCredentialsRevoker):
    """What this application withdraws a holder's credentials through."""
