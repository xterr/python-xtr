"""A client registered without scopes gets the ones this deployment defaults to."""

from __future__ import annotations

import pytest
from xtr_event_dispatcher import EventDispatcher

from tests.support.models import client_model
from xtr_security_oauth2_server.event.pre_save_client_event import PreSaveClientEvent
from xtr_security_oauth2_server.event_listener.add_client_default_scopes_listener import (
    AddClientDefaultScopesListener,
)
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.value_object.scope import Scope

pytestmark = pytest.mark.anyio


def test_it_gives_a_scopeless_client_the_default_scopes() -> None:
    event = PreSaveClientEvent(client_model())
    listener = AddClientDefaultScopesListener(("read", "write"))

    listener(event)

    assert event.get_client().get_scopes() == (Scope("read"), Scope("write"))


def test_it_leaves_a_client_that_already_has_scopes_alone() -> None:
    event = PreSaveClientEvent(client_model(scopes=("admin",)))
    listener = AddClientDefaultScopesListener(("read",))

    listener(event)

    assert event.get_client().get_scopes() == (Scope("admin"),)


def test_it_leaves_a_scopeless_client_scopeless_when_there_is_no_default() -> None:
    event = PreSaveClientEvent(client_model())
    listener = AddClientDefaultScopesListener(())

    listener(event)

    assert event.get_client().get_scopes() == ()


def test_it_works_on_the_client_the_event_carries_now() -> None:
    event = PreSaveClientEvent(client_model("client-1"))
    event.set_client(client_model("client-2"))
    listener = AddClientDefaultScopesListener(("read",))

    listener(event)

    assert event.get_client().get_identifier() == "client-2"
    assert event.get_client().get_scopes() == (Scope("read"),)


async def test_a_dispatcher_calling_it_as_a_listener_reaches_it() -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener(
        OAuth2Events.PRE_SAVE_CLIENT,
        AddClientDefaultScopesListener(("read",)),
    )
    manager = ClientManager(dispatcher)

    await manager.save(client_model())

    stored = await manager.find("client-1")
    assert stored is not None
    assert stored.get_scopes() == (Scope("read"),)
