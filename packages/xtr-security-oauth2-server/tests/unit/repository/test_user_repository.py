"""Who the credentials a client sent belong to, asked of the application."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entity_builders import client_entity
from tests.support.models import client_model
from tests.support.users import SecurityUser
from xtr_security_oauth2_server.converter.user_converter import UserConverter
from xtr_security_oauth2_server.event.user_resolve_event import UserResolveEvent
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from xtr_security_oauth2_server.repository.user_repository import UserRepository
from xtr_security_oauth2_server.value_object.grant import Grant

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


async def _repository(
    dispatcher: RecordingEventDispatcher | None = None,
) -> tuple[UserRepository, RecordingEventDispatcher]:
    recording = dispatcher if dispatcher is not None else RecordingEventDispatcher()
    clients = ClientManager(RecordingEventDispatcher())
    await clients.save(client_model("client-1"))

    return UserRepository(clients, recording, UserConverter()), recording


def _resolve_to(identifier: str) -> Callable[[object], None]:
    def listener(event: object) -> None:
        assert isinstance(event, UserResolveEvent)
        _ = event.set_user(SecurityUser(identifier))

    return listener


async def test_it_satisfies_the_user_repository_contract() -> None:
    repository, _ = await _repository()

    assert UserRepositoryInterface in UserRepository.__mro__
    assert isinstance(repository, UserRepositoryInterface)


async def test_it_resolves_nobody_when_no_listener_does() -> None:
    repository, _ = await _repository()

    resolved = await repository.get_user_entity_by_user_credentials(
        "someone",
        "s3cret",
        "password",
        client_entity(),
    )

    assert resolved is None


async def test_it_resolves_the_user_a_listener_found() -> None:
    dispatcher = RecordingEventDispatcher()
    dispatcher.listen(OAuth2Events.USER_RESOLVE, _resolve_to("user-1"))
    repository, _ = await _repository(dispatcher)

    resolved = await repository.get_user_entity_by_user_credentials(
        "someone",
        "s3cret",
        "password",
        client_entity(),
    )

    assert resolved is not None
    assert resolved.get_identifier() == "user-1"


async def test_it_asks_under_the_name_a_listener_registers_by() -> None:
    repository, dispatcher = await _repository()

    _ = await repository.get_user_entity_by_user_credentials(
        "someone",
        "s3cret",
        "password",
        client_entity(),
    )

    dispatched = dispatcher.only()
    assert isinstance(dispatched.event, UserResolveEvent)
    assert dispatched.name == OAuth2Events.USER_RESOLVE


async def test_what_it_asks_carries_the_credentials_the_grant_and_the_client() -> None:
    repository, dispatcher = await _repository()

    _ = await repository.get_user_entity_by_user_credentials(
        "someone",
        "s3cret",
        "password",
        client_entity(),
    )

    event = dispatcher.only().event
    assert isinstance(event, UserResolveEvent)
    assert event.get_username() == "someone"
    assert event.get_password() == "s3cret"
    assert event.get_grant() == Grant("password")
    assert event.get_client().get_identifier() == "client-1"


async def test_it_refuses_to_ask_for_a_client_nobody_stored() -> None:
    repository, _ = await _repository()

    with pytest.raises(InvalidArgumentError, match="unknown-client"):
        _ = await repository.get_user_entity_by_user_credentials(
            "someone",
            "s3cret",
            "password",
            client_entity("unknown-client"),
        )
