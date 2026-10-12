"""Withdrawing the token a client hands over, and saying no more than that it is done."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_http_message import Response

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entities import make_client
from tests.support.grants import Storage
from tests.support.handlers import wire_handler
from tests.support.messages import body_of, server_request
from tests.support.signing import make_clock
from tests.support.tokens import sealed_refresh_token, signed_access_token
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.handlers.token_revocation_handler import TokenRevocationHandler
from xtr_security_oauth2_server.handlers.validated_token import ValidatedToken

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface


@final
class _ReadingHandler(TokenRevocationHandler):
    """A handler whose reading of the token is whatever the test decided."""

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        read: ValidatedToken | None,
    ) -> None:
        super().__init__(dispatcher, clock)
        self._read: ValidatedToken | None = read
        self.asked: list[tuple[ServerRequestInterface, str]] = []

    @override
    async def validate_token(
        self,
        request: ServerRequestInterface,
        client: ClientEntityInterface,
    ) -> ValidatedToken | None:
        self.asked.append((request, client.get_identifier()))

        return self._read


def _request(**body: str) -> ServerRequestInterface:
    return server_request(
        "POST",
        "https://authorization.example.com/revoke",
        parsed_body={"client_id": "client-1", "client_secret": "secret", **body},
    )


def _registered() -> Storage:
    storage = Storage()
    storage.clients.add(make_client("client-1"), "secret")

    return storage


def _reading(read: ValidatedToken | None, storage: Storage) -> _ReadingHandler:
    handler = _ReadingHandler(RecordingEventDispatcher(), make_clock(), read)
    wire_handler(handler, storage)

    return handler


def _handler(storage: Storage) -> TokenRevocationHandler:
    handler = TokenRevocationHandler(RecordingEventDispatcher(), make_clock())
    wire_handler(handler, storage)

    return handler


@pytest.mark.anyio
async def test_an_access_token_of_the_asking_client_is_withdrawn() -> None:
    storage = _registered()
    read = ValidatedToken("access_token", {"jti": "access-1", "aud": ["client-1"]})
    handler = _reading(read, storage)
    request = _request(token="token-1")

    answer = await handler.respond_to_request(request, Response())

    assert answer.get_status_code() == 200
    assert handler.asked == [(request, "client-1")]
    assert await storage.access_tokens.is_access_token_revoked("access-1")


@pytest.mark.anyio
async def test_a_refresh_token_takes_the_access_token_it_came_with() -> None:
    storage = _registered()
    read = ValidatedToken(
        "refresh_token",
        {"refresh_token_id": "refresh-1", "access_token_id": "access-1"},
    )
    handler = _reading(read, storage)

    answer = await handler.respond_to_request(_request(token="token-1"), Response())

    assert answer.get_status_code() == 200
    assert await storage.refresh_tokens.is_refresh_token_revoked("refresh-1")
    assert await storage.access_tokens.is_access_token_revoked("access-1")


@pytest.mark.anyio
async def test_a_token_this_server_will_not_speak_for_is_answered_all_the_same() -> None:
    storage = _registered()
    handler = _reading(None, storage)

    answer = await handler.respond_to_request(_request(token="token-1"), Response())

    assert answer.get_status_code() == 200
    assert storage.access_tokens.revoked == set()
    assert storage.refresh_tokens.revoked == set()


@pytest.mark.anyio
async def test_a_refresh_token_naming_no_access_token_is_withdrawn_on_its_own() -> None:
    storage = _registered()
    read = ValidatedToken("refresh_token", {"refresh_token_id": "refresh-1"})
    handler = _reading(read, storage)

    answer = await handler.respond_to_request(_request(token="token-1"), Response())

    assert answer.get_status_code() == 200
    assert await storage.refresh_tokens.is_refresh_token_revoked("refresh-1")
    assert storage.access_tokens.revoked == set()


@pytest.mark.anyio
async def test_a_request_from_an_unauthenticated_client_is_refused() -> None:
    storage = _registered()
    handler = _handler(storage)
    request = _request(token="token-1", client_secret="wrong")

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.respond_to_request(request, Response())

    assert refusal.value.get_code() == 4
    assert refusal.value.get_error_type() == "invalid_client"


@pytest.mark.anyio
async def test_a_request_naming_no_token_is_refused() -> None:
    handler = _handler(_registered())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.respond_to_request(_request(), Response())

    assert refusal.value.get_code() == 3
    assert refusal.value.get_error_type() == "invalid_request"


@pytest.mark.anyio
async def test_another_clients_access_token_is_left_standing() -> None:
    storage = _registered()
    read = ValidatedToken("access_token", {"jti": "access-1", "aud": ["client-2"]})
    handler = _reading(read, storage)

    answer = await handler.respond_to_request(_request(token="token-1"), Response())

    assert answer.get_status_code() == 200
    assert storage.access_tokens.revoked == set()


@pytest.mark.anyio
async def test_an_access_token_naming_the_asking_client_as_its_client_is_withdrawn() -> None:
    storage = _registered()
    read = ValidatedToken("access_token", {"jti": "access-1", "client_id": "client-1"})
    handler = _reading(read, storage)

    _ = await handler.respond_to_request(_request(token="token-1"), Response())

    assert await storage.access_tokens.is_access_token_revoked("access-1")


@pytest.mark.anyio
async def test_a_token_read_as_a_third_kind_is_refused() -> None:
    storage = _registered()
    handler = _reading(ValidatedToken("saml2_token", {}), storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.respond_to_request(_request(token="token-1"), Response())

    assert refusal.value.get_error_type() == "unsupported_token_type"


@pytest.mark.anyio
async def test_the_answer_says_nothing_at_all_and_may_not_be_cached() -> None:
    handler = _reading(None, _registered())

    answer = await handler.respond_to_request(_request(token="token-1"), Response())

    assert body_of(answer) == ""
    assert answer.get_header_line("cache-control") == "no-store"


@pytest.mark.anyio
async def test_a_real_access_token_of_the_asking_client_is_withdrawn() -> None:
    storage = _registered()
    handler = _handler(storage)

    answer = await handler.respond_to_request(
        _request(token=signed_access_token()),
        Response(),
    )

    assert answer.get_status_code() == 200
    assert await storage.access_tokens.is_access_token_revoked("access-1")


@pytest.mark.anyio
async def test_a_real_refresh_token_takes_the_access_token_it_came_with() -> None:
    storage = _registered()
    handler = _handler(storage)

    answer = await handler.respond_to_request(
        _request(token=sealed_refresh_token()),
        Response(),
    )

    assert answer.get_status_code() == 200
    assert await storage.refresh_tokens.is_refresh_token_revoked("refresh-1")
    assert await storage.access_tokens.is_access_token_revoked("access-1")


@pytest.mark.anyio
async def test_a_real_token_from_another_authorization_server_is_answered_the_same_way() -> None:
    storage = _registered()
    handler = _handler(storage)
    token = signed_access_token(issuer="https://other.example.com")

    answer = await handler.respond_to_request(_request(token=token), Response())

    assert answer.get_status_code() == 200
    assert storage.access_tokens.revoked == set()


@pytest.mark.anyio
async def test_a_real_expired_access_token_is_answered_the_same_way() -> None:
    storage = _registered()
    handler = _handler(storage)
    token = signed_access_token(lifetime=timedelta(seconds=-1))

    answer = await handler.respond_to_request(_request(token=token), Response())

    assert answer.get_status_code() == 200
    assert storage.access_tokens.revoked == set()


@pytest.mark.anyio
async def test_another_clients_real_refresh_token_is_left_standing() -> None:
    storage = _registered()
    handler = _handler(storage)
    token = sealed_refresh_token(client_id="client-2")

    answer = await handler.respond_to_request(_request(token=token), Response())

    assert answer.get_status_code() == 200
    assert storage.refresh_tokens.revoked == set()
    assert storage.access_tokens.revoked == set()
