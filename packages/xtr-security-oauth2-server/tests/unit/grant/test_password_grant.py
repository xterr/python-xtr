"""A client that has seen the resource owner's own credentials exchanges them."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entities import make_client, make_user
from tests.support.grants import Storage, wire
from tests.support.messages import server_request
from tests.support.repositories import InMemoryRefreshTokenRepository, InMemoryScopeRepository
from tests.support.response_types import RecordingResponseType
from tests.support.signing import make_clock
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.grant.password_grant import PasswordGrant
from xtr_security_oauth2_server.request_event import RequestEvent

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

_AN_HOUR = timedelta(hours=1)


def _token_request(**body: str) -> ServerRequestInterface:
    return server_request("POST", "/token", parsed_body=body)


def _credentials(**extra: str) -> ServerRequestInterface:
    body = {
        "client_id": "client-1",
        "client_secret": "secret",
        "username": "alice",
        "password": "letmein",
        **extra,
    }

    return server_request("POST", "/token", parsed_body=body)


def _grant(
    storage: Storage,
    default_scope: str = "",
) -> tuple[PasswordGrant, RecordingEventDispatcher]:
    storage.clients.add(make_client("client-1"), "secret")
    storage.users.add("alice", "letmein", make_user("user-1"))
    dispatcher = RecordingEventDispatcher()
    grant = PasswordGrant(dispatcher, make_clock(), storage.users, storage.refresh_tokens)
    wire(grant, storage, default_scope=default_scope)

    return grant, dispatcher


def test_it_is_asked_for_by_name() -> None:
    grant, _ = _grant(Storage())

    assert grant.get_identifier() == "password"


@pytest.mark.anyio
async def test_the_right_credentials_are_handed_an_access_token_for_the_user() -> None:
    storage = Storage()
    grant, _ = _grant(storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(_credentials(), response_type, _AN_HOUR)

    assert response_type.access_token is not None
    assert response_type.access_token.get_user_identifier() == "user-1"


@pytest.mark.anyio
async def test_a_refresh_token_is_handed_out_beside_it() -> None:
    storage = Storage()
    grant, _ = _grant(storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(_credentials(), response_type, _AN_HOUR)

    assert response_type.refresh_token is not None
    assert response_type.refresh_token.get_access_token() is response_type.access_token


@pytest.mark.anyio
async def test_both_tokens_are_announced_in_the_order_they_were_issued() -> None:
    storage = Storage()
    grant, dispatcher = _grant(storage)

    _ = await grant.respond_to_access_token_request(
        _credentials(),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert dispatcher.names() == (
        RequestEvent.ACCESS_TOKEN_ISSUED,
        RequestEvent.REFRESH_TOKEN_ISSUED,
    )


@pytest.mark.anyio
async def test_the_user_repository_is_asked_on_behalf_of_this_grant_and_client() -> None:
    storage = Storage()
    grant, _ = _grant(storage)

    _ = await grant.respond_to_access_token_request(
        _credentials(),
        RecordingResponseType(),
        _AN_HOUR,
    )

    asked = storage.users.asked[0]
    assert asked.username == "alice"
    assert asked.grant_type == "password"
    assert asked.client_identifier == "client-1"


@pytest.mark.anyio
async def test_wrong_credentials_are_refused_and_the_failure_announced() -> None:
    storage = Storage()
    grant, dispatcher = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _credentials(password="guess"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_grant"
    assert dispatcher.names() == (RequestEvent.USER_AUTHENTICATION_FAILED,)


@pytest.mark.anyio
async def test_a_request_naming_no_user_is_refused() -> None:
    storage = Storage()
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(client_id="client-1", client_secret="secret", password="letmein"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_request"
    assert "username" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_request_carrying_no_password_is_refused() -> None:
    storage = Storage()
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(client_id="client-1", client_secret="secret", username="alice"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_request"
    assert "password" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_the_scopes_are_finalised_for_the_resource_owner_they_are_granted_to() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read", "write"))
    grant, _ = _grant(storage)

    _ = await grant.respond_to_access_token_request(
        _credentials(scope="read"),
        RecordingResponseType(),
        _AN_HOUR,
    )

    call = storage.scopes.finalized[0]
    assert [scope.get_identifier() for scope in call.scopes] == ["read"]
    assert call.grant_type == "password"
    assert call.user_identifier == "user-1"


@pytest.mark.anyio
async def test_a_request_naming_no_scope_asks_for_the_default_one() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read"))
    grant, _ = _grant(storage, default_scope="read")

    _ = await grant.respond_to_access_token_request(
        _credentials(),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert [scope.get_identifier() for scope in storage.scopes.finalized[0].scopes] == ["read"]


@pytest.mark.anyio
async def test_the_scopes_are_read_before_the_credentials_are_checked() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read"))
    grant, dispatcher = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _credentials(password="guess", scope="delete"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_scope"
    assert dispatcher.dispatched == []


@pytest.mark.anyio
async def test_no_refresh_token_is_handed_out_when_the_repository_mints_none() -> None:
    storage = Storage(refresh_tokens=InMemoryRefreshTokenRepository(issues=False))
    grant, dispatcher = _grant(storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(_credentials(), response_type, _AN_HOUR)

    assert response_type.refresh_token is None
    assert dispatcher.names() == (RequestEvent.ACCESS_TOKEN_ISSUED,)
