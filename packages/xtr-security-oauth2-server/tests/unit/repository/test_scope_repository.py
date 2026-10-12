"""Which scopes this server knows, and what a token is finally granted."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.repositories.scope_repository_interface import (
    ScopeRepositoryInterface,
)

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entity_builders import client_entity, scope_entities
from tests.support.models import client_model
from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.event.scope_resolve_event import ScopeResolveEvent
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.manager.in_memory.scope_manager import ScopeManager
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.repository.scope_repository import ScopeRepository
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

pytestmark = pytest.mark.anyio


async def _repository(
    available: Sequence[str] = ("read", "write"),
    client_scopes: Sequence[str] = (),
    dispatcher: RecordingEventDispatcher | None = None,
) -> tuple[ScopeRepository, RecordingEventDispatcher]:
    recording = dispatcher if dispatcher is not None else RecordingEventDispatcher()
    clients = ClientManager(RecordingEventDispatcher())
    await clients.save(client_model("client-1", scopes=client_scopes))

    return (
        ScopeRepository(ScopeManager(available), clients, ScopeConverter(), recording),
        recording,
    )


def _narrow_to(*kept: str) -> Callable[[object], None]:
    def listener(event: object) -> None:
        assert isinstance(event, ScopeResolveEvent)
        _ = event.set_scopes(*(Scope(name) for name in kept))

    return listener


async def test_it_satisfies_the_scope_repository_contract() -> None:
    repository, _ = await _repository()

    assert ScopeRepositoryInterface in ScopeRepository.__mro__
    assert isinstance(repository, ScopeRepositoryInterface)


async def test_it_finds_a_scope_this_deployment_made_available() -> None:
    repository, _ = await _repository()

    found = await repository.get_scope_entity_by_identifier("read")

    assert found is not None
    assert found.get_identifier() == "read"


async def test_it_finds_nothing_for_a_scope_nobody_made_available() -> None:
    repository, _ = await _repository()

    assert await repository.get_scope_entity_by_identifier("admin") is None


async def test_a_client_with_no_scopes_is_granted_what_it_asked_for() -> None:
    repository, _ = await _repository()

    granted = await repository.finalize_scopes(
        scope_entities("read"),
        "client_credentials",
        client_entity(),
    )

    assert [str(scope) for scope in granted] == ["read"]


async def test_a_client_with_scopes_that_asked_for_none_is_granted_its_own() -> None:
    repository, _ = await _repository(client_scopes=("read", "write"))

    granted = await repository.finalize_scopes((), "client_credentials", client_entity())

    assert [str(scope) for scope in granted] == ["read", "write"]


async def test_a_client_with_scopes_is_granted_the_ones_it_asked_for() -> None:
    repository, _ = await _repository(client_scopes=("read", "write"))

    granted = await repository.finalize_scopes(
        scope_entities("write"),
        "client_credentials",
        client_entity(),
    )

    assert [str(scope) for scope in granted] == ["write"]


async def test_a_client_asking_for_a_scope_it_does_not_hold_is_refused() -> None:
    repository, _ = await _repository(client_scopes=("read",))

    with pytest.raises(OAuthServerError, match="scope") as refusal:
        _ = await repository.finalize_scopes(
            scope_entities("write"),
            "client_credentials",
            client_entity(),
        )

    assert refusal.value.get_error_type() == "invalid_scope"


async def test_a_client_with_no_scopes_and_asking_for_none_is_granted_none() -> None:
    repository, _ = await _repository()

    granted = await repository.finalize_scopes((), "client_credentials", client_entity())

    assert granted == ()


async def test_it_announces_the_scopes_before_settling_them() -> None:
    repository, dispatcher = await _repository(client_scopes=("read", "write"))

    _ = await repository.finalize_scopes(
        scope_entities("read"),
        "authorization_code",
        client_entity(),
        "user-1",
    )

    dispatched = dispatcher.only()
    assert isinstance(dispatched.event, ScopeResolveEvent)
    assert dispatched.name == OAuth2Events.SCOPE_RESOLVE


async def test_what_it_announces_carries_the_grant_the_client_and_the_owner() -> None:
    repository, dispatcher = await _repository()

    _ = await repository.finalize_scopes(
        scope_entities("read"),
        "authorization_code",
        client_entity(),
        "user-1",
    )

    event = dispatcher.only().event
    assert isinstance(event, ScopeResolveEvent)
    assert event.get_grant() == Grant("authorization_code")
    assert event.get_client().get_identifier() == "client-1"
    assert event.get_user_identifier() == "user-1"
    assert event.get_scopes() == (Scope("read"),)


async def test_what_a_listener_leaves_behind_is_what_is_granted() -> None:
    dispatcher = RecordingEventDispatcher()
    dispatcher.listen(OAuth2Events.SCOPE_RESOLVE, _narrow_to("read"))
    repository, _ = await _repository(dispatcher=dispatcher)

    granted = await repository.finalize_scopes(
        scope_entities("read", "write"),
        "client_credentials",
        client_entity(),
    )

    assert [str(scope) for scope in granted] == ["read"]


async def test_a_listener_can_leave_a_token_with_no_scope_at_all() -> None:
    dispatcher = RecordingEventDispatcher()
    dispatcher.listen(OAuth2Events.SCOPE_RESOLVE, _narrow_to())
    repository, _ = await _repository(dispatcher=dispatcher)

    granted = await repository.finalize_scopes(
        scope_entities("read"),
        "client_credentials",
        client_entity(),
    )

    assert granted == ()


async def test_it_hands_back_entities_a_grant_can_put_on_a_token() -> None:
    repository, _ = await _repository()

    granted = await repository.finalize_scopes(
        scope_entities("read"),
        "client_credentials",
        client_entity(),
    )

    assert all(hasattr(scope, "get_identifier") for scope in granted)


async def test_it_refuses_to_settle_scopes_for_a_client_nobody_stored() -> None:
    repository, _ = await _repository()

    with pytest.raises(InvalidArgumentError, match="unknown-client"):
        _ = await repository.finalize_scopes(
            (),
            "client_credentials",
            client_entity("unknown-client"),
        )


async def test_the_code_being_redeemed_is_handed_in_for_a_listener_to_read() -> None:
    repository, _ = await _repository()

    granted = await repository.finalize_scopes(
        scope_entities("read"),
        "authorization_code",
        client_entity(),
        "user-1",
        "ac-1",
    )

    assert [str(scope) for scope in granted] == ["read"]
