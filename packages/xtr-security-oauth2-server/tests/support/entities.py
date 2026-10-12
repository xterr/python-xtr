"""Concrete entities built out of the shipped traits, for the tests to use.

The library ships contracts and traits, never a concrete entity: an
application composes its own. These are what an application would write, so a
test exercising a trait exercises it the way it will actually be used, and a
test asserting a contract asserts it against something that satisfies it by
composition rather than by a hand-written double.

``Client`` carries its own setters because the client trait holds its
registration as protected state with readers only — the entity that composes
it decides how it is filled, from a constructor, a row or a setter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_oauth2_server.entities.traits.access_token_trait import AccessTokenTrait
from xtr_security_oauth2_server.entities.traits.auth_code_trait import AuthCodeTrait
from xtr_security_oauth2_server.entities.traits.client_trait import ClientTrait
from xtr_security_oauth2_server.entities.traits.device_code_trait import DeviceCodeTrait
from xtr_security_oauth2_server.entities.traits.entity_trait import EntityTrait
from xtr_security_oauth2_server.entities.traits.refresh_token_trait import RefreshTokenTrait
from xtr_security_oauth2_server.entities.traits.scope_trait import ScopeTrait
from xtr_security_oauth2_server.entities.traits.token_entity_trait import TokenEntityTrait

if TYPE_CHECKING:
    from collections.abc import Sequence


class Scope(EntityTrait, ScopeTrait):
    """A scope named by its identifier."""


class User(EntityTrait):
    """A resource owner named by its identifier."""


@final
class Client(EntityTrait, ClientTrait):
    """A registered client, filled through setters of its own."""

    def set_name(self, name: str) -> None:
        self._name = name

    def set_redirect_uri(self, redirect_uri: str | Sequence[str]) -> None:
        self._redirect_uri = redirect_uri

    def set_confidential(self, confidential: bool) -> None:
        self._is_confidential = confidential


class AccessToken(EntityTrait, TokenEntityTrait, AccessTokenTrait):
    """An access token that signs itself into a JWT."""


class AuthCode(EntityTrait, TokenEntityTrait, AuthCodeTrait):
    """An authorization code carrying the redirect URI it was asked for."""


class RefreshToken(EntityTrait, RefreshTokenTrait):
    """A refresh token tied to the access token it was issued beside."""


class DeviceCode(EntityTrait, TokenEntityTrait, DeviceCodeTrait):
    """A device code with the user code its owner types in."""


def make_scope(identifier: str) -> Scope:
    """Return a scope named ``identifier``."""
    scope = Scope()
    scope.set_identifier(identifier)
    return scope


def make_scopes(*identifiers: str) -> tuple[Scope, ...]:
    """Return one scope per identifier, in the order given."""
    return tuple(make_scope(identifier) for identifier in identifiers)


def make_user(identifier: str = "user-1") -> User:
    """Return a user named ``identifier``."""
    user = User()
    user.set_identifier(identifier)
    return user


def make_client(
    identifier: str = "client-1",
    name: str = "Test client",
    redirect_uri: str | Sequence[str] = "https://client.example.com/callback",
    *,
    confidential: bool = True,
) -> Client:
    """Return a registered client with the given registration."""
    client = Client()
    client.set_identifier(identifier)
    client.set_name(name)
    client.set_redirect_uri(redirect_uri)
    client.set_confidential(confidential)
    return client
