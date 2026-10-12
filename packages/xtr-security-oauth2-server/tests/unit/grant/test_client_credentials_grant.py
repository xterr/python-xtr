"""A client acting for itself exchanges its own credentials for a token."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entities import make_client
from tests.support.grants import Storage, wire
from tests.support.messages import server_request
from tests.support.repositories import InMemoryScopeRepository
from tests.support.response_types import RecordingResponseType
from tests.support.signing import make_clock
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.grant.client_credentials_grant import ClientCredentialsGrant
from xtr_security_oauth2_server.request_event import RequestEvent

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

_AN_HOUR = timedelta(hours=1)


def _token_request(**body: str) -> ServerRequestInterface:
    return server_request("POST", "/token", parsed_body=body)


def _grant(
    storage: Storage,
    default_scope: str = "",
) -> tuple[ClientCredentialsGrant, RecordingEventDispatcher]:
    dispatcher = RecordingEventDispatcher()
    grant = ClientCredentialsGrant(dispatcher, make_clock())
    wire(grant, storage, default_scope=default_scope)

    return grant, dispatcher


def _confidential(storage: Storage) -> None:
    storage.clients.add(make_client("client-1"), "secret")


def test_it_is_asked_for_by_name() -> None:
    grant, _ = _grant(Storage())

    assert grant.get_identifier() == "client_credentials"


@pytest.mark.anyio
async def test_a_confidential_client_is_handed_an_access_token() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    response_type = RecordingResponseType()

    answered = await grant.respond_to_access_token_request(
        _token_request(client_id="client-1", client_secret="secret"),
        response_type,
        _AN_HOUR,
    )

    assert answered is response_type
    assert response_type.access_token is not None


@pytest.mark.anyio
async def test_the_token_it_hands_out_names_no_resource_owner() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(client_id="client-1", client_secret="secret"),
        response_type,
        _AN_HOUR,
    )

    assert response_type.access_token is not None
    assert response_type.access_token.get_user_identifier() is None


@pytest.mark.anyio
async def test_it_hands_out_no_refresh_token() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(client_id="client-1", client_secret="secret"),
        response_type,
        _AN_HOUR,
    )

    assert response_type.refresh_token is None


@pytest.mark.anyio
async def test_the_token_it_hands_out_is_announced() -> None:
    storage = Storage()
    _confidential(storage)
    grant, dispatcher = _grant(storage)

    _ = await grant.respond_to_access_token_request(
        _token_request(client_id="client-1", client_secret="secret"),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert dispatcher.names() == (RequestEvent.ACCESS_TOKEN_ISSUED,)


@pytest.mark.anyio
async def test_a_public_client_is_refused_and_the_failure_announced() -> None:
    storage = Storage()
    storage.clients.add(make_client("client-1", confidential=False))
    grant, dispatcher = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(client_id="client-1"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_client"
    assert dispatcher.names() == (RequestEvent.CLIENT_AUTHENTICATION_FAILED,)


@pytest.mark.anyio
async def test_the_scopes_asked_for_are_finalised_without_a_resource_owner() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read", "write"))
    _confidential(storage)
    grant, _ = _grant(storage)

    _ = await grant.respond_to_access_token_request(
        _token_request(client_id="client-1", client_secret="secret", scope="read write"),
        RecordingResponseType(),
        _AN_HOUR,
    )

    call = storage.scopes.finalized[0]
    assert [scope.get_identifier() for scope in call.scopes] == ["read", "write"]
    assert call.grant_type == "client_credentials"
    assert call.user_identifier is None
    assert call.auth_code_id is None


@pytest.mark.anyio
async def test_a_request_naming_no_scope_asks_for_the_default_one() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read"))
    _confidential(storage)
    grant, _ = _grant(storage, default_scope="read")

    _ = await grant.respond_to_access_token_request(
        _token_request(client_id="client-1", client_secret="secret"),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert [scope.get_identifier() for scope in storage.scopes.finalized[0].scopes] == ["read"]


@pytest.mark.anyio
async def test_an_unknown_scope_is_refused() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read"))
    _confidential(storage)
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(client_id="client-1", client_secret="secret", scope="delete"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_scope"


@pytest.mark.anyio
async def test_the_token_carries_the_scopes_that_were_finalised() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read", "write"))
    _confidential(storage)
    grant, _ = _grant(storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(client_id="client-1", client_secret="secret", scope="read"),
        response_type,
        _AN_HOUR,
    )

    assert response_type.access_token is not None
    assert [scope.get_identifier() for scope in response_type.access_token.get_scopes()] == ["read"]
