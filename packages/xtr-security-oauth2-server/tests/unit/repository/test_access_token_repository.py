"""Minting an access token, storing it, and withdrawing it again."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from joserfc import jwt as joserfc_jwt
from xtr_clock import MockClock

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entity_builders import access_token_entity, client_entity, scope_entities
from tests.support.models import LATER, NOW, client_model
from tests.support.signing import SIGNING_KEY, make_signer
from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.event.access_token_extra_claims_resolve_event import (
    AccessTokenExtraClaimsResolveEvent,
)
from xtr_security_oauth2_server.exception import (
    UniqueTokenIdentifierConstraintViolationError,
)
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.manager.in_memory.access_token_manager import AccessTokenManager
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)
from xtr_security_oauth2_server.repository.access_token_repository import AccessTokenRepository
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

pytestmark = pytest.mark.anyio


async def _repository(
    dispatcher: RecordingEventDispatcher | None = None,
) -> tuple[AccessTokenRepository, AccessTokenManager, RecordingEventDispatcher]:
    recording = dispatcher if dispatcher is not None else RecordingEventDispatcher()
    tokens = AccessTokenManager(MockClock(NOW))
    clients = ClientManager(RecordingEventDispatcher())
    await clients.save(client_model("client-1"))

    return (
        AccessTokenRepository(tokens, clients, ScopeConverter(), recording),
        tokens,
        recording,
    )


def _ask_for(claims: Mapping[str, object]) -> Callable[[object], None]:
    def listener(event: object) -> None:
        assert isinstance(event, AccessTokenExtraClaimsResolveEvent)
        _ = event.set_extra_claims(claims)

    return listener


async def test_it_satisfies_the_access_token_repository_contract() -> None:
    repository, _, _ = await _repository()

    assert AccessTokenRepositoryInterface in AccessTokenRepository.__mro__
    assert isinstance(repository, AccessTokenRepositoryInterface)


async def test_it_mints_a_token_for_the_client_it_was_given() -> None:
    repository, _, _ = await _repository()

    token = await repository.get_new_token(client_entity(), scope_entities("read"), "user-1")

    assert token.get_client().get_identifier() == "client-1"


async def test_it_mints_a_token_carrying_the_scopes_it_was_given() -> None:
    repository, _, _ = await _repository()

    token = await repository.get_new_token(client_entity(), scope_entities("read", "write"))

    assert [str(scope) for scope in token.get_scopes()] == ["read", "write"]


async def test_it_mints_a_token_for_the_resource_owner_it_was_given() -> None:
    repository, _, _ = await _repository()

    token = await repository.get_new_token(client_entity(), (), "user-1")

    assert token.get_user_identifier() == "user-1"


async def test_it_mints_a_token_naming_nobody_when_the_client_acts_for_itself() -> None:
    repository, _, _ = await _repository()

    token = await repository.get_new_token(client_entity(), ())

    assert token.get_user_identifier() is None


async def test_an_empty_resource_owner_is_as_good_as_none() -> None:
    repository, _, _ = await _repository()

    token = await repository.get_new_token(client_entity(), (), "")

    assert token.get_user_identifier() is None


async def test_it_asks_what_else_the_token_should_say_before_minting_it() -> None:
    repository, _, dispatcher = await _repository()

    _ = await repository.get_new_token(client_entity(), scope_entities("read"), "user-1")

    dispatched = dispatcher.only()
    assert isinstance(dispatched.event, AccessTokenExtraClaimsResolveEvent)
    assert dispatched.name == OAuth2Events.ACCESS_TOKEN_EXTRA_CLAIMS_RESOLVE


async def test_what_it_asks_carries_the_client_the_scopes_and_the_owner() -> None:
    repository, _, dispatcher = await _repository()

    _ = await repository.get_new_token(client_entity(), scope_entities("read"), "user-1")

    event = dispatcher.only().event
    assert isinstance(event, AccessTokenExtraClaimsResolveEvent)
    assert event.get_client().get_identifier() == "client-1"
    assert [str(scope) for scope in event.get_scopes()] == ["read"]
    assert event.get_user_identifier() == "user-1"


async def test_the_claims_a_listener_asked_for_are_put_on_the_token() -> None:
    dispatcher = RecordingEventDispatcher()
    dispatcher.listen(
        OAuth2Events.ACCESS_TOKEN_EXTRA_CLAIMS_RESOLVE,
        _ask_for({"tenant": "acme"}),
    )
    repository, _, _ = await _repository(dispatcher)

    token = await repository.get_new_token(client_entity(), (), "user-1")
    token.set_identifier("at-1")
    token.set_expiry_date_time(LATER)
    token.set_private_key(make_signer())

    decoded = joserfc_jwt.decode(token.to_string(), SIGNING_KEY)
    assert decoded.claims["tenant"] == "acme"


async def test_a_listener_asking_for_a_claim_the_token_mints_itself_is_refused() -> None:
    dispatcher = RecordingEventDispatcher()
    dispatcher.listen(
        OAuth2Events.ACCESS_TOKEN_EXTRA_CLAIMS_RESOLVE,
        _ask_for({"iss": "somewhere-else"}),
    )
    repository, _, _ = await _repository(dispatcher)

    with pytest.raises(InvalidArgumentError, match="iss"):
        _ = await repository.get_new_token(client_entity(), (), "user-1")


async def test_it_stores_what_was_issued() -> None:
    repository, tokens, _ = await _repository()

    await repository.persist_new_access_token(access_token_entity(scopes=("read",)))

    stored = await tokens.find("at-1")
    assert stored is not None
    assert stored.get_scopes() == (Scope("read"),)
    assert stored.get_user_identifier() == "user-1"
    assert stored.get_client().get_identifier() == "client-1"


async def test_it_refuses_an_identifier_already_taken() -> None:
    repository, _, _ = await _repository()
    await repository.persist_new_access_token(access_token_entity())

    with pytest.raises(UniqueTokenIdentifierConstraintViolationError):
        await repository.persist_new_access_token(access_token_entity())


async def test_it_refuses_to_store_a_token_for_a_client_nobody_stored() -> None:
    repository, _, _ = await _repository()
    entity = access_token_entity(client=client_entity("unknown-client"))

    with pytest.raises(InvalidArgumentError, match="unknown-client"):
        await repository.persist_new_access_token(entity)


async def test_it_withdraws_a_token_it_stored() -> None:
    repository, tokens, _ = await _repository()
    await repository.persist_new_access_token(access_token_entity())

    await repository.revoke_access_token("at-1")

    stored = await tokens.find("at-1")
    assert stored is not None
    assert stored.is_revoked() is True


async def test_withdrawing_a_token_it_never_stored_is_no_error() -> None:
    repository, _, _ = await _repository()

    await repository.revoke_access_token("nope")


async def test_a_token_it_never_stored_counts_as_withdrawn() -> None:
    repository, _, _ = await _repository()

    assert await repository.is_access_token_revoked("nope") is True


async def test_a_token_it_stored_is_not_withdrawn() -> None:
    repository, _, _ = await _repository()
    await repository.persist_new_access_token(access_token_entity())

    assert await repository.is_access_token_revoked("at-1") is False


async def test_a_token_it_withdrew_reports_as_withdrawn() -> None:
    repository, _, _ = await _repository()
    await repository.persist_new_access_token(access_token_entity())

    await repository.revoke_access_token("at-1")

    assert await repository.is_access_token_revoked("at-1") is True
