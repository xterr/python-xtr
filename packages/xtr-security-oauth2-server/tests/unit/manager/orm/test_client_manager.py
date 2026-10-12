"""The stored clients, announced before each save and listed on criteria."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.app_client import AuditAppClient
from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.models import client_model
from tests.support.orm import CONNECTION, connections_of, orm_driver, stored
from xtr_security_oauth2_server.event.pre_save_client_event import PreSaveClientEvent
from xtr_security_oauth2_server.manager.client_filter import ClientFilter
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.manager.orm.client_manager import ClientManager
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.support.orm import Database

pytestmark = pytest.mark.anyio


def test_it_declares_the_client_manager_contract() -> None:
    assert ClientManagerInterface in ClientManager.__mro__


def _manager(database: Database) -> tuple[ClientManager, RecordingEventDispatcher]:
    """Return a manager on a session of its own, and the dispatcher it announces through."""
    dispatcher = RecordingEventDispatcher()

    return (
        ClientManager(connections_of(database.session()), CONNECTION, dispatcher, Client),
        dispatcher,
    )


async def test_it_finds_a_client_it_stored(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)
        await manager.save(client_model(grants=("password",), scopes=("read",)))

        found = await manager.find("client-1")

        assert found is not None
        assert found.get_name() == "Test client"
        assert found.get_secret() == "hashed-secret"
        assert found.get_grants() == (Grant("password"),)
        assert found.get_scopes() == (Scope("read"),)
        assert found.is_active() is True
        assert found.is_plain_text_pkce_allowed() is False


async def test_it_finds_nothing_under_an_unknown_identifier(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)

        assert await manager.find("nope") is None


async def test_it_announces_a_client_before_storing_it(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, dispatcher = _manager(database)

        await manager.save(client_model())

        assert list(dispatcher.names()) == [OAuth2Events.PRE_SAVE_CLIENT]
        assert isinstance(dispatcher.only().event, PreSaveClientEvent)


async def test_it_stores_the_client_a_listener_put_on_the_event(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, dispatcher = _manager(database)
        dispatcher.listen(
            OAuth2Events.PRE_SAVE_CLIENT,
            _replace_with(client_model("replacement")),
        )

        await manager.save(client_model("asked-for"))

        assert await manager.find("replacement") is not None
        assert await manager.find("asked-for") is None


async def test_a_saved_client_is_committed_so_another_session_reads_it(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)

        await manager.save(client_model())

        second, _ = _manager(database)
        assert await second.find("client-1") is not None


async def test_it_forgets_a_client_it_removed(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)
        await manager.save(client_model())
        found = await manager.find("client-1")
        assert found is not None

        await manager.remove(found)

        assert await manager.find("client-1") is None
        assert await database.count("oauth2_client") == 0


async def test_it_lists_every_client_when_nothing_narrows_the_listing(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)
        await manager.save(client_model("one"))
        await manager.save(client_model("two"))

        assert len(await manager.list(None)) == 2
        assert len(await manager.list(ClientFilter.create())) == 2


async def test_it_lists_only_the_clients_holding_a_named_grant(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)
        await manager.save(client_model("with", grants=("password",)))
        await manager.save(client_model("without", grants=("implicit",)))

        listed = await manager.list(ClientFilter.create().add_grant_criteria(Grant("password")))

        assert [client.get_identifier() for client in listed] == ["with"]


async def test_a_value_stored_between_two_others_is_matched(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)
        await manager.save(
            client_model("middle", grants=("authorization_code", "refresh_token", "password")),
        )

        listed = await manager.list(
            ClientFilter.create().add_grant_criteria(Grant("refresh_token")),
        )

        assert [client.get_identifier() for client in listed] == ["middle"]


async def test_a_client_has_to_hold_every_value_named_of_one_kind(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)
        await manager.save(client_model("both", grants=("password", "implicit")))
        await manager.save(client_model("one-of-them", grants=("password",)))

        listed = await manager.list(
            ClientFilter.create().add_grant_criteria(Grant("password"), Grant("implicit")),
        )

        assert [client.get_identifier() for client in listed] == ["both"]


async def test_a_client_has_to_meet_every_kind_of_criterion_named(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)
        await manager.save(client_model("both", grants=("password",), scopes=("read",)))
        await manager.save(client_model("grant-only", grants=("password",), scopes=("write",)))

        listed = await manager.list(
            ClientFilter.create()
            .add_grant_criteria(Grant("password"))
            .add_scope_criteria(Scope("read")),
        )

        assert [client.get_identifier() for client in listed] == ["both"]


async def test_it_lists_only_the_clients_registered_with_a_named_redirect_uri(
    tmp_path: Path,
) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)
        await manager.save(client_model("with", redirect_uris=("https://a.example.com/cb",)))
        await manager.save(client_model("without", redirect_uris=("https://b.example.com/cb",)))

        listed = await manager.list(
            ClientFilter.create().add_redirect_uri_criteria(
                RedirectUri("https://a.example.com/cb"),
            ),
        )

        assert [client.get_identifier() for client in listed] == ["with"]


async def test_a_client_holding_nothing_of_a_named_kind_is_left_out(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)
        await manager.save(client_model("open"))

        listed = await manager.list(ClientFilter.create().add_grant_criteria(Grant("implicit")))

        assert listed == ()


async def test_a_criterion_carrying_a_wildcard_matches_itself_only(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        manager, _ = _manager(database)
        await manager.save(client_model("plain", redirect_uris=("https://a.example.com/cb",)))

        listed = await manager.list(
            ClientFilter.create().add_redirect_uri_criteria(RedirectUri("https://%")),
        )

        assert listed == ()


async def test_it_finds_a_client_by_its_identifier_and_not_by_its_primary_key(
    tmp_path: Path,
) -> None:
    driver = orm_driver(client_class=AuditAppClient)
    async with stored(tmp_path, driver, AuditAppClient.metadata) as database:
        session = database.session()
        manager = ClientManager(
            connections_of(session),
            CONNECTION,
            RecordingEventDispatcher(),
            AuditAppClient,
        )
        await manager.save(AuditAppClient("App", "client-1", "hashed-secret"))

        found = await manager.find("client-1")

        assert found is not None
        assert found.get_name() == "App"


def _replace_with(replacement: Client) -> Callable[[object], None]:
    """Return a listener that puts ``replacement`` on the event it is handed."""

    def listener(event: object) -> None:
        assert isinstance(event, PreSaveClientEvent)
        event.set_client(replacement)

    return listener
