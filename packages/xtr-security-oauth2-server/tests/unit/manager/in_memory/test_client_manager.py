"""Clients kept in this process, announced before each save and listed on criteria."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.models import client_model
from xtr_security_oauth2_server.event.pre_save_client_event import PreSaveClientEvent
from xtr_security_oauth2_server.manager.client_filter import ClientFilter
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_security_oauth2_server.model.client import Client

pytestmark = pytest.mark.anyio


def _manager(
    dispatcher: RecordingEventDispatcher | None = None,
) -> tuple[ClientManager, RecordingEventDispatcher]:
    recording = dispatcher if dispatcher is not None else RecordingEventDispatcher()

    return ClientManager(recording), recording


def test_it_declares_the_client_manager_contract() -> None:
    assert ClientManagerInterface in ClientManager.__mro__


async def test_it_finds_a_client_it_stored() -> None:
    manager, _ = _manager()
    client = client_model()

    await manager.save(client)

    assert await manager.find("client-1") is client


async def test_it_finds_nothing_under_an_unknown_identifier() -> None:
    manager, _ = _manager()

    assert await manager.find("nope") is None


async def test_it_forgets_a_client_it_removed() -> None:
    manager, _ = _manager()
    client = client_model()
    await manager.save(client)

    await manager.remove(client)

    assert await manager.find("client-1") is None


async def test_removing_a_client_it_never_stored_changes_nothing() -> None:
    manager, _ = _manager()

    await manager.remove(client_model())

    assert await manager.find("client-1") is None


async def test_it_announces_a_client_before_storing_it() -> None:
    manager, dispatcher = _manager()

    await manager.save(client_model())

    dispatched = dispatcher.only()
    assert isinstance(dispatched.event, PreSaveClientEvent)
    assert dispatched.name == OAuth2Events.PRE_SAVE_CLIENT


async def test_it_stores_the_client_a_listener_put_on_the_event() -> None:
    dispatcher = RecordingEventDispatcher()
    replacement = client_model("client-1", name="Replaced")
    dispatcher.listen(OAuth2Events.PRE_SAVE_CLIENT, _replace_client_with(replacement))
    manager, _ = _manager(dispatcher)

    await manager.save(client_model())

    assert await manager.find("client-1") is replacement


async def test_it_lists_every_client_when_nothing_narrows_the_listing() -> None:
    manager, _ = _manager()
    await manager.save(client_model("client-1"))
    await manager.save(client_model("client-2"))

    listed = await manager.list(None)

    assert [client.get_identifier() for client in listed] == ["client-1", "client-2"]


async def test_it_lists_every_client_when_the_filter_narrows_nothing() -> None:
    manager, _ = _manager()
    await manager.save(client_model("client-1"))

    listed = await manager.list(ClientFilter.create())

    assert [client.get_identifier() for client in listed] == ["client-1"]


async def test_it_lists_only_the_clients_holding_a_named_grant() -> None:
    manager, _ = _manager()
    await manager.save(client_model("with", grants=("password",)))
    await manager.save(client_model("without", grants=("implicit",)))

    listed = await manager.list(ClientFilter.create().add_grant_criteria(Grant("password")))

    assert [client.get_identifier() for client in listed] == ["with"]


async def test_it_lists_only_the_clients_holding_a_named_scope() -> None:
    manager, _ = _manager()
    await manager.save(client_model("with", scopes=("read",)))
    await manager.save(client_model("without", scopes=("write",)))

    listed = await manager.list(ClientFilter.create().add_scope_criteria(Scope("read")))

    assert [client.get_identifier() for client in listed] == ["with"]


async def test_it_lists_only_the_clients_holding_a_named_redirect_uri() -> None:
    manager, _ = _manager()
    await manager.save(client_model("with", redirect_uris=("https://a.example.com/cb",)))
    await manager.save(client_model("without", redirect_uris=("https://b.example.com/cb",)))

    criteria = ClientFilter.create().add_redirect_uri_criteria(
        RedirectUri("https://a.example.com/cb"),
    )

    assert [client.get_identifier() for client in await manager.list(criteria)] == ["with"]


async def test_a_client_must_meet_every_kind_of_criterion_named() -> None:
    manager, _ = _manager()
    await manager.save(client_model("both", grants=("password",), scopes=("read",)))
    await manager.save(client_model("grant-only", grants=("password",), scopes=("write",)))

    criteria = (
        ClientFilter.create()
        .add_grant_criteria(Grant("password"))
        .add_scope_criteria(Scope("read"))
    )

    assert [client.get_identifier() for client in await manager.list(criteria)] == ["both"]


async def test_a_client_has_to_hold_every_value_named_of_one_kind() -> None:
    manager, _ = _manager()
    await manager.save(client_model("both", grants=("password", "implicit")))
    await manager.save(client_model("one-of-them", grants=("password",)))

    criteria = ClientFilter.create().add_grant_criteria(Grant("password"), Grant("implicit"))

    assert [client.get_identifier() for client in await manager.list(criteria)] == ["both"]


def _replace_client_with(replacement: Client) -> Callable[[object], None]:
    def listener(event: object) -> None:
        assert isinstance(event, PreSaveClientEvent)
        event.set_client(replacement)

    return listener
