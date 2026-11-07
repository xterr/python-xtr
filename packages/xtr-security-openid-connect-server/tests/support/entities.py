"""Concrete entities built out of the authorization server's traits.

The authorization server ships traits, never a concrete entity: an application
composes its own. These are what an application would write, so the ID-token
tests read an access token signed exactly as a deployment's would be.
"""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server_core.entities.traits.access_token_trait import AccessTokenTrait
from xtr_security_oauth2_server_core.entities.traits.client_trait import ClientTrait
from xtr_security_oauth2_server_core.entities.traits.entity_trait import EntityTrait
from xtr_security_oauth2_server_core.entities.traits.scope_trait import ScopeTrait
from xtr_security_oauth2_server_core.entities.traits.token_entity_trait import TokenEntityTrait

__all__ = ["AccessToken", "Client", "Scope", "make_client", "make_scope"]


@final
class Scope(EntityTrait, ScopeTrait):
    """A scope named by its identifier."""


@final
class Client(EntityTrait, ClientTrait):
    """A registered client, named by its identifier."""


@final
class AccessToken(EntityTrait, TokenEntityTrait, AccessTokenTrait):
    """An access token that signs itself into a JWT."""


def make_scope(identifier: str) -> Scope:
    """Return a scope named ``identifier``."""
    scope = Scope()
    scope.set_identifier(identifier)
    return scope


def make_client(identifier: str = "my-client") -> Client:
    """Return a client named ``identifier``."""
    client = Client()
    client.set_identifier(identifier)
    return client
