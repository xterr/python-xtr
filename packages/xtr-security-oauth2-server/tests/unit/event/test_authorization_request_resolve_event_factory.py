"""Building the consent event out of a request, a stored client and a resource owner."""

from __future__ import annotations

import pytest
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.request_types.authorization_request import AuthorizationRequest

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.models import client_model
from tests.support.users import SecurityUser
from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.entity.client import Client as ClientEntity
from xtr_security_oauth2_server.entity.scope import Scope as ScopeEntity
from xtr_security_oauth2_server.event.authorization_request_resolve_event_factory import (
    AuthorizationRequestResolveEventFactory,
)
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.value_object.scope import Scope

pytestmark = pytest.mark.anyio


def _client_entity(identifier: str = "client-1") -> ClientEntity:
    client = ClientEntity()
    client.set_identifier(identifier)
    client.set_name("Test client")
    client.set_redirect_uri([])
    client.set_confidential(True)

    return client


def _scope_entity(identifier: str) -> ScopeEntity:
    scope = ScopeEntity()
    scope.set_identifier(identifier)

    return scope


def _authorization_request(client_identifier: str = "client-1") -> AuthorizationRequest:
    request = AuthorizationRequest()
    request.set_grant_type_id("authorization_code")
    request.set_client(_client_entity(client_identifier))
    request.set_scopes((_scope_entity("read"), _scope_entity("write")))

    return request


async def _factory() -> AuthorizationRequestResolveEventFactory:
    manager = ClientManager(RecordingEventDispatcher())
    await manager.save(client_model("client-1", name="Stored client"))

    return AuthorizationRequestResolveEventFactory(ScopeConverter(), manager)


async def test_it_carries_the_stored_client_the_request_named() -> None:
    factory = await _factory()

    event = await factory.from_authorization_request(_authorization_request(), SecurityUser())

    assert event.get_client().get_name() == "Stored client"


async def test_it_carries_the_requested_scopes_as_stored_scopes() -> None:
    factory = await _factory()

    event = await factory.from_authorization_request(_authorization_request(), SecurityUser())

    assert event.get_scopes() == (Scope("read"), Scope("write"))


async def test_it_carries_the_resource_owner_it_was_handed() -> None:
    factory = await _factory()
    user = SecurityUser("someone")

    event = await factory.from_authorization_request(_authorization_request(), user)

    assert event.get_user() is user


async def test_the_event_it_builds_reports_the_request_it_was_built_from() -> None:
    factory = await _factory()

    event = await factory.from_authorization_request(_authorization_request(), SecurityUser())

    assert event.get_grant_type_id() == "authorization_code"


async def test_it_refuses_a_request_naming_a_client_nobody_stored() -> None:
    factory = await _factory()

    with pytest.raises(InvalidArgumentError, match="unknown-client"):
        _ = await factory.from_authorization_request(
            _authorization_request("unknown-client"),
            SecurityUser(),
        )
