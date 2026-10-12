"""The browser is handed the token itself, in the fragment."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import pytest
from xtr_http_message import Response

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entities import make_client, make_user
from tests.support.grants import Storage, wire
from tests.support.messages import server_request
from tests.support.repositories import InMemoryScopeRepository
from tests.support.response_types import RecordingResponseType
from tests.support.signing import FROZEN_NOW, make_clock
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.grant.implicit_grant import ImplicitGrant
from xtr_security_oauth2_server.request_event import RequestEvent

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

_AN_HOUR = timedelta(hours=1)
_CALLBACK = "https://client.example.com/callback"


def _authorize_request(**query: str) -> ServerRequestInterface:
    return server_request("GET", "/authorize", query_params=query)


def _grant(storage: Storage) -> tuple[ImplicitGrant, RecordingEventDispatcher]:
    dispatcher = RecordingEventDispatcher()
    grant = ImplicitGrant(dispatcher, make_clock(), _AN_HOUR)
    wire(grant, storage)

    return grant, dispatcher


def _registered(storage: Storage) -> None:
    storage.clients.add(make_client("client-1", confidential=False))


async def _approved(grant: ImplicitGrant, **query: str) -> str:
    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="token", client_id="client-1", **query),
    )
    authorization_request.set_user(make_user("user-1"))
    authorization_request.set_authorization_approved(True)
    answered = await grant.complete_authorization_request(
        _authorize_request(),
        authorization_request,
    )

    return answered.generate_http_response(Response()).get_header_line("location")


def test_it_is_asked_for_by_name() -> None:
    grant, _ = _grant(Storage())

    assert grant.get_identifier() == "implicit"


def test_it_answers_no_token_request() -> None:
    grant, _ = _grant(Storage())
    request = server_request("POST", "/token", parsed_body={"grant_type": "implicit"})

    assert grant.can_respond_to_access_token_request(request) is False


@pytest.mark.anyio
async def test_asking_it_to_answer_a_token_request_says_it_cannot() -> None:
    grant, _ = _grant(Storage())
    request = server_request("POST", "/token")

    with pytest.raises(InvalidArgumentError, match="token endpoint"):
        _ = await grant.respond_to_access_token_request(
            request,
            RecordingResponseType(),
            _AN_HOUR,
        )


def test_it_refuses_to_be_given_a_refresh_token_lifetime() -> None:
    grant, _ = _grant(Storage())

    with pytest.raises(InvalidArgumentError, match="refresh token"):
        grant.set_refresh_token_ttl(timedelta(days=30))


def test_it_refuses_to_be_given_a_refresh_token_repository() -> None:
    storage = Storage()
    grant, _ = _grant(storage)

    with pytest.raises(InvalidArgumentError, match="refresh token"):
        grant.set_refresh_token_repository(storage.refresh_tokens)


def test_it_answers_an_authorization_request_asking_for_a_token() -> None:
    grant, _ = _grant(Storage())
    request = _authorize_request(response_type="token", client_id="client-1")

    assert grant.can_respond_to_authorization_request(request) is True


def test_it_does_not_answer_an_authorization_request_asking_for_a_code() -> None:
    grant, _ = _grant(Storage())
    request = _authorize_request(response_type="code", client_id="client-1")

    assert grant.can_respond_to_authorization_request(request) is False


@pytest.mark.anyio
async def test_a_validated_request_records_what_was_asked_for() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read"))
    _registered(storage)
    grant, _ = _grant(storage)

    authorization_request = await grant.validate_authorization_request(
        _authorize_request(
            response_type="token",
            client_id="client-1",
            redirect_uri=_CALLBACK,
            state="xyz",
            scope="read",
        ),
    )

    assert authorization_request.get_grant_type_id() == "implicit"
    assert authorization_request.get_redirect_uri() == _CALLBACK
    assert authorization_request.get_state() == "xyz"
    assert [scope.get_identifier() for scope in authorization_request.get_scopes()] == ["read"]


@pytest.mark.anyio
async def test_it_asks_for_no_code_challenge() -> None:
    storage = Storage()
    _registered(storage)
    grant, _ = _grant(storage)

    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="token", client_id="client-1"),
    )

    assert authorization_request.get_code_challenge() is None


@pytest.mark.anyio
async def test_an_unknown_scope_is_refused_into_the_fragment() -> None:
    storage = Storage()
    _registered(storage)
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_authorization_request(
            _authorize_request(
                response_type="token",
                client_id="client-1",
                scope="delete",
                state="xyz",
            ),
        )

    assert refusal.value.get_redirect_uri() == f"{_CALLBACK}#state=xyz"


@pytest.mark.anyio
async def test_an_approved_request_hands_the_token_back_in_the_fragment() -> None:
    storage = Storage()
    _registered(storage)
    grant, _ = _grant(storage)

    location = await _approved(grant, state="xyz")
    fragment = parse_qs(urlsplit(location).fragment)

    assert urlsplit(location).query == ""
    assert fragment["token_type"] == ["Bearer"]
    assert fragment["expires_in"] == ["3600"]
    assert fragment["state"] == ["xyz"]
    assert fragment["access_token"][0].count(".") == 2


@pytest.mark.anyio
async def test_the_token_it_hands_back_is_announced() -> None:
    storage = Storage()
    _registered(storage)
    grant, dispatcher = _grant(storage)

    _ = await _approved(grant)

    assert dispatcher.names() == (RequestEvent.ACCESS_TOKEN_ISSUED,)


@pytest.mark.anyio
async def test_the_scopes_are_finalised_for_the_resource_owner() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read"))
    _registered(storage)
    grant, _ = _grant(storage)

    _ = await _approved(grant, scope="read")

    call = storage.scopes.finalized[-1]
    assert call.grant_type == "implicit"
    assert call.user_identifier == "user-1"


@pytest.mark.anyio
async def test_the_token_expires_after_the_lifetime_the_grant_was_built_with() -> None:
    storage = Storage()
    _registered(storage)
    grant, _ = _grant(storage)

    _ = await _approved(grant)

    stored = next(iter(storage.access_tokens.tokens.values()))
    assert stored.get_expiry_date_time() == FROZEN_NOW + _AN_HOUR


@pytest.mark.anyio
async def test_a_refused_request_sends_the_browser_back_with_the_refusal() -> None:
    storage = Storage()
    _registered(storage)
    grant, _ = _grant(storage)
    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="token", client_id="client-1", state="xyz"),
    )
    authorization_request.set_user(make_user("user-1"))

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.complete_authorization_request(
            _authorize_request(),
            authorization_request,
        )

    assert refusal.value.get_error_type() == "access_denied"
    assert refusal.value.get_redirect_uri() == f"{_CALLBACK}#state=xyz"


@pytest.mark.anyio
async def test_completing_a_request_nobody_decided_on_names_the_missing_user() -> None:
    storage = Storage()
    _registered(storage)
    grant, _ = _grant(storage)
    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="token", client_id="client-1"),
    )

    with pytest.raises(InvalidArgumentError, match="resource owner"):
        _ = await grant.complete_authorization_request(
            _authorize_request(),
            authorization_request,
        )
