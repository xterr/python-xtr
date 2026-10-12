"""The scopes a deployment defaults to reach the client that is registered with none."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel

from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.event_listener.add_client_default_scopes_listener import (
    AddClientDefaultScopesListener,
)
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.scope import Scope

pytestmark = pytest.mark.anyio


def _configured() -> Kernel:
    """Return a kernel of the application defaulting a client to ``read``."""
    return Kernel(
        "tests.fixtures.oauth2_server_app",
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
    )


async def test_a_client_registered_with_no_scopes_gets_the_configured_defaults() -> None:
    async with await _configured().boot() as booted:
        clients = await booted.container.get(ClientManagerInterface)

        await clients.save(Client("A client", "scope-less", None))
        found = await clients.find("scope-less")

        assert found is not None
        assert [str(scope) for scope in found.get_scopes()] == ["read"]


async def test_a_client_registered_with_scopes_of_its_own_keeps_exactly_those() -> None:
    async with await _configured().boot() as booted:
        clients = await booted.container.get(ClientManagerInterface)
        chosen = Client("A client", "narrowed", None)
        _ = chosen.set_scopes(Scope("write"))

        await clients.save(chosen)
        found = await clients.find("narrowed")

        assert found is not None
        assert [str(scope) for scope in found.get_scopes()] == ["write"]


async def test_the_listener_is_built_with_the_configured_defaults() -> None:
    async with await _configured().boot() as booted:
        listener = await booted.container.get(AddClientDefaultScopesListener)

    assert repr(listener) == "AddClientDefaultScopesListener(default_scopes=('read',))"
