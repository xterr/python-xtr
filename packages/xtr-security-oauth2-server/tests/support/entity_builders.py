"""Builders for the shipped entities, so a bridge test says only what it cares about.

The repository bridges are handed entities a grant would have filled in, and
building one takes four or five setter calls that have nothing to do with what
a test is about. Everything here builds a real shipped entity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_oauth2_server.entity.access_token import AccessToken
from xtr_security_oauth2_server.entity.auth_code import AuthCode
from xtr_security_oauth2_server.entity.client import Client
from xtr_security_oauth2_server.entity.device_code import DeviceCode
from xtr_security_oauth2_server.entity.refresh_token import RefreshToken
from xtr_security_oauth2_server.entity.scope import Scope

from .models import LATER

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

__all__ = [
    "access_token_entity",
    "auth_code_entity",
    "client_entity",
    "device_code_entity",
    "refresh_token_entity",
    "scope_entities",
    "scope_entity",
]


def scope_entity(identifier: str) -> Scope:
    """Return the scope entity named ``identifier``."""
    scope = Scope()
    scope.set_identifier(identifier)

    return scope


def scope_entities(*identifiers: str) -> tuple[Scope, ...]:
    """Return one scope entity per identifier, in the order given."""
    return tuple(scope_entity(identifier) for identifier in identifiers)


def client_entity(
    identifier: str = "client-1",
    name: str = "Test client",
    redirect_uris: Sequence[str] = (),
    *,
    confidential: bool = True,
) -> Client:
    """Return the client entity a grant would have been handed."""
    client = Client()
    client.set_identifier(identifier)
    client.set_name(name)
    client.set_redirect_uri(redirect_uris)
    client.set_confidential(confidential)

    return client


def access_token_entity(
    identifier: str = "at-1",
    expiry: datetime = LATER,
    client: Client | None = None,
    user_identifier: str | None = "user-1",
    scopes: Sequence[str] = (),
) -> AccessToken:
    """Return the access-token entity a grant would have filled in."""
    token = AccessToken()
    token.set_identifier(identifier)
    token.set_expiry_date_time(expiry)
    token.set_client(client if client is not None else client_entity())
    if user_identifier is not None:
        token.set_user_identifier(user_identifier)
    for scope in scopes:
        token.add_scope(scope_entity(scope))

    return token


def auth_code_entity(
    identifier: str = "ac-1",
    expiry: datetime = LATER,
    client: Client | None = None,
    user_identifier: str | None = "user-1",
    scopes: Sequence[str] = (),
) -> AuthCode:
    """Return the authorization-code entity a grant would have filled in."""
    code = AuthCode()
    code.set_identifier(identifier)
    code.set_expiry_date_time(expiry)
    code.set_client(client if client is not None else client_entity())
    if user_identifier is not None:
        code.set_user_identifier(user_identifier)
    for scope in scopes:
        code.add_scope(scope_entity(scope))

    return code


def refresh_token_entity(
    identifier: str = "rt-1",
    expiry: datetime = LATER,
    access_token: AccessToken | None = None,
) -> RefreshToken:
    """Return the refresh-token entity a grant would have filled in."""
    token = RefreshToken()
    token.set_identifier(identifier)
    token.set_expiry_date_time(expiry)
    token.set_access_token(access_token if access_token is not None else access_token_entity())

    return token


def device_code_entity(
    identifier: str = "dc-1",
    expiry: datetime = LATER,
    user_code: str = "BCDFGHJK",
    client: Client | None = None,
    *,
    user_identifier: str | None = None,
    scopes: Sequence[str] = (),
    user_approved: bool = False,
    last_polled_at: datetime | None = None,
    interval: int = 5,
    include_verification_uri_complete: bool = False,
) -> DeviceCode:
    """Return the device-code entity a grant would have filled in."""
    code = DeviceCode()
    code.set_identifier(identifier)
    code.set_expiry_date_time(expiry)
    code.set_client(client if client is not None else client_entity())
    code.set_user_code(user_code)
    code.set_verification_uri("https://authorization.example.com/device")
    code.set_interval(interval)
    code.set_user_approved(user_approved)
    code.set_verification_uri_complete_in_auth_response(include_verification_uri_complete)
    if user_identifier is not None:
        code.set_user_identifier(user_identifier)
    if last_polled_at is not None:
        code.set_last_polled_at(last_polled_at)
    for scope in scopes:
        code.add_scope(scope_entity(scope))

    return code
