"""Builders for the stored models, so a test says only what it cares about.

The managers and the repository bridges all deal in the same five models, and
a test about expiry has no business spelling out a client, a user identifier
and a scope list to get one. Everything here builds a real model — nothing is
a double — and every parameter has a default a test can leave alone.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.authorization_code import AuthorizationCode
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.model.device_code import DeviceCode
from xtr_security_oauth2_server.model.refresh_token import RefreshToken
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.model.client_interface import ClientInterface

#: Where the frozen clock of these tests stands.
NOW: Final[datetime] = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)

#: An expiry comfortably after :data:`NOW`.
LATER: Final[datetime] = datetime(2026, 3, 4, 6, 6, 7, tzinfo=UTC)

#: An expiry comfortably before :data:`NOW`.
EARLIER: Final[datetime] = datetime(2026, 3, 4, 4, 6, 7, tzinfo=UTC)

#: The stored hash a client defaults to here. Not a password: the models hold
#: hashes, and the recording hasher of these tests reads this shape.
_HASH: Final[str] = "hashed-secret"


def client_model(
    identifier: str = "client-1",
    secret: str | None = _HASH,
    name: str = "Test client",
    *,
    grants: Sequence[str] = (),
    scopes: Sequence[str] = (),
    redirect_uris: Sequence[str] = (),
    active: bool = True,
) -> Client:
    """Return a stored client with the registration a test names."""
    client = Client(name, identifier, secret)
    _ = client.set_grants(*(Grant(grant) for grant in grants))
    _ = client.set_scopes(*(Scope(scope) for scope in scopes))
    _ = client.set_redirect_uris(*(RedirectUri(uri) for uri in redirect_uris))
    _ = client.set_active(active)

    return client


def access_token_model(
    identifier: str = "at-1",
    expiry: datetime = LATER,
    client: ClientInterface | None = None,
    user_identifier: str | None = "user-1",
    scopes: Sequence[str] = (),
) -> AccessToken:
    """Return a stored access token with the window and scopes a test names."""
    return AccessToken(
        identifier,
        expiry,
        client if client is not None else client_model(),
        user_identifier,
        tuple(Scope(scope) for scope in scopes),
    )


def authorization_code_model(
    identifier: str = "ac-1",
    expiry: datetime = LATER,
    client: ClientInterface | None = None,
    user_identifier: str | None = "user-1",
    scopes: Sequence[str] = (),
) -> AuthorizationCode:
    """Return a stored authorization code with the window and scopes a test names."""
    return AuthorizationCode(
        identifier,
        expiry,
        client if client is not None else client_model(),
        user_identifier,
        tuple(Scope(scope) for scope in scopes),
    )


def refresh_token_model(
    identifier: str = "rt-1",
    expiry: datetime = LATER,
    access_token: AccessToken | None = None,
) -> RefreshToken:
    """Return a stored refresh token tied to ``access_token``, if any."""
    return RefreshToken(identifier, expiry, access_token)


def device_code_model(
    identifier: str = "dc-1",
    expiry: datetime = LATER,
    user_code: str = "BCDFGHJK",
    client: ClientInterface | None = None,
    *,
    user_identifier: str | None = None,
    scopes: Sequence[str] = (),
    user_approved: bool = False,
    last_polled_at: datetime | None = None,
    interval: int = 5,
    include_verification_uri_complete: bool = False,
) -> DeviceCode:
    """Return a stored device code with the codes and polling state a test names."""
    return DeviceCode(
        identifier,
        expiry,
        client if client is not None else client_model(),
        user_identifier,
        tuple(Scope(scope) for scope in scopes),
        user_code,
        user_approved,
        "https://authorization.example.com/device",
        last_polled_at,
        interval,
        include_verification_uri_complete=include_verification_uri_complete,
    )
