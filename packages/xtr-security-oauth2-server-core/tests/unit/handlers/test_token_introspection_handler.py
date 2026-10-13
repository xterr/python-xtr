"""Answering what this server will say about the token a client hands over."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_http_message import Response

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entities import make_client
from tests.support.grants import Storage
from tests.support.handlers import wire_handler
from tests.support.messages import document_of, server_request
from tests.support.signing import FROZEN_NOW, ISSUER, make_clock
from tests.support.tokens import A_MONTH, AN_HOUR, sealed_refresh_token, signed_access_token
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.handlers.token_introspection_handler import (
    TokenIntrospectionHandler,
)
from xtr_security_oauth2_server_core.handlers.validated_token import ValidatedToken

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )


@final
class _ReadingHandler(TokenIntrospectionHandler):
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


@final
class _RecordingResponseType:
    """A document that records what it was told, and answers the response it was given."""

    def __init__(self) -> None:
        self.told: list[tuple[str, object]] = []
        self.built: list[object] = []

    def set_active(self, active: bool) -> None:
        """Record the liveness it was told."""
        self.told.append(("active", active))

    def set_token_type(self, token_type: str) -> None:
        """Record the kind of token it was told."""
        self.told.append(("token_type", token_type))

    def set_token_data(self, token_data: Mapping[str, object]) -> None:
        """Record what the token carries."""
        self.told.append(("token_data", dict(token_data)))

    async def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        """Answer the response it was handed, untouched."""
        self.told.append(("response", response))
        self.built.append(self)

        return response


def _request(**body: str) -> ServerRequestInterface:
    return server_request(
        "POST",
        "https://authorization.example.com/introspect",
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


def _handler(storage: Storage) -> TokenIntrospectionHandler:
    handler = TokenIntrospectionHandler(RecordingEventDispatcher(), make_clock())
    wire_handler(handler, storage)

    return handler


async def _body(answer: ResponseInterface) -> Mapping[str, object]:
    return cast("Mapping[str, object]", await document_of(answer))


@pytest.mark.anyio
async def test_an_access_token_is_answered_as_what_it_claims() -> None:
    handler = _reading(ValidatedToken("access_token", {"jti": "access-1"}), _registered())
    request = _request(token="token-1")

    answer = await handler.respond_to_request(request, Response())

    assert answer.get_status_code() == 200
    assert answer.get_header_line("content-type") == "application/json; charset=UTF-8"
    assert await _body(answer) == {
        "active": True,
        "scope": "",
        "token_type": "Bearer",
        "jti": "access-1",
    }
    assert handler.asked == [(request, "client-1")]


@pytest.mark.anyio
async def test_a_refresh_token_is_answered_as_the_payload_it_was_sealed_from() -> None:
    read = ValidatedToken("refresh_token", {"refresh_token_id": "refresh-1"})
    handler = _reading(read, _registered())

    answer = await handler.respond_to_request(_request(token="token-1"), Response())

    assert answer.get_status_code() == 200
    assert answer.get_header_line("content-type") == "application/json; charset=UTF-8"
    assert await _body(answer) == {"active": True, "scope": "", "jti": "refresh-1"}


@pytest.mark.anyio
async def test_a_token_this_server_will_not_speak_for_says_nothing_is_live() -> None:
    handler = _reading(None, _registered())

    answer = await handler.respond_to_request(_request(token="token-1"), Response())

    assert answer.get_status_code() == 200
    assert answer.get_header_line("content-type") == "application/json; charset=UTF-8"
    assert await _body(answer) == {"active": False}


@pytest.mark.anyio
async def test_the_document_it_was_given_is_the_one_the_answer_is_built_by() -> None:
    read = ValidatedToken("foo", {"bar": "baz"})
    handler = _reading(read, _registered())
    response_type = _RecordingResponseType()
    handler.set_response_type(response_type)
    response = Response()

    answer = await handler.respond_to_request(_request(token="token-1"), response)

    assert answer is response
    assert response_type.told == [
        ("active", True),
        ("token_type", "foo"),
        ("token_data", {"bar": "baz"}),
        ("response", response),
    ]


@pytest.mark.anyio
async def test_each_request_is_answered_by_its_own_copy_of_the_document() -> None:
    handler = _reading(ValidatedToken("foo", {}), _registered())
    response_type = _RecordingResponseType()
    handler.set_response_type(response_type)

    _ = await handler.respond_to_request(_request(token="token-1"), Response())
    _ = await handler.respond_to_request(_request(token="token-2"), Response())

    first, second = response_type.built
    assert first is not response_type
    assert second is not first


@pytest.mark.anyio
async def test_a_request_from_an_unauthenticated_client_is_refused() -> None:
    handler = _handler(_registered())
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
async def test_a_real_live_access_token_is_answered_with_what_it_says() -> None:
    handler = _handler(_registered())

    answer = await handler.respond_to_request(
        _request(token=signed_access_token()),
        Response(),
    )

    body = await _body(answer)
    assert body["active"] is True
    assert body["client_id"] == "client-1"
    assert body["sub"] == "user-1"
    assert body["scope"] == "read"
    assert body["jti"] == "access-1"
    assert body["iss"] == ISSUER
    assert body["token_type"] == "Bearer"
    assert body["exp"] == int((FROZEN_NOW + AN_HOUR).timestamp())


@pytest.mark.anyio
async def test_a_real_revoked_access_token_says_nothing_is_live() -> None:
    storage = _registered()
    await storage.access_tokens.revoke_access_token("access-1")
    handler = _handler(storage)

    answer = await handler.respond_to_request(
        _request(token=signed_access_token()),
        Response(),
    )

    assert await _body(answer) == {"active": False}


@pytest.mark.anyio
async def test_a_real_expired_access_token_says_nothing_is_live() -> None:
    handler = _handler(_registered())
    token = signed_access_token(lifetime=timedelta(seconds=-1))

    answer = await handler.respond_to_request(_request(token=token), Response())

    assert await _body(answer) == {"active": False}


@pytest.mark.anyio
async def test_another_clients_real_access_token_is_answered_for_what_it_says() -> None:
    handler = _handler(_registered())
    token = signed_access_token(client_id="client-2")

    answer = await handler.respond_to_request(_request(token=token), Response())

    body = await _body(answer)
    assert body["active"] is True
    assert body["client_id"] == "client-2"


@pytest.mark.anyio
async def test_a_real_token_from_another_authorization_server_says_nothing_is_live() -> None:
    handler = _handler(_registered())
    token = signed_access_token(issuer="https://other.example.com")

    answer = await handler.respond_to_request(_request(token=token), Response())

    assert await _body(answer) == {"active": False}


@pytest.mark.anyio
async def test_something_that_is_not_a_token_says_nothing_is_live() -> None:
    handler = _handler(_registered())

    answer = await handler.respond_to_request(_request(token="whatever"), Response())

    assert await _body(answer) == {"active": False}


@pytest.mark.anyio
async def test_a_real_live_refresh_token_is_answered_with_what_it_knows() -> None:
    handler = _handler(_registered())

    answer = await handler.respond_to_request(
        _request(token=sealed_refresh_token()),
        Response(),
    )

    body = await _body(answer)
    assert body["active"] is True
    assert body["client_id"] == "client-1"
    assert body["sub"] == "user-1"
    assert body["scope"] == "read"
    assert body["jti"] == "refresh-1"
    assert body["exp"] == int((FROZEN_NOW + A_MONTH).timestamp())


@pytest.mark.anyio
async def test_a_real_revoked_refresh_token_says_nothing_is_live() -> None:
    storage = _registered()
    _ = await storage.refresh_tokens.revoke_refresh_token("refresh-1")
    handler = _handler(storage)

    answer = await handler.respond_to_request(
        _request(token=sealed_refresh_token()),
        Response(),
    )

    assert await _body(answer) == {"active": False}


@pytest.mark.anyio
async def test_a_real_expired_refresh_token_says_nothing_is_live() -> None:
    handler = _handler(_registered())
    token = sealed_refresh_token(lifetime=timedelta(seconds=-1))

    answer = await handler.respond_to_request(_request(token=token), Response())

    assert await _body(answer) == {"active": False}


@pytest.mark.anyio
async def test_a_kind_of_token_this_server_knows_nothing_about_is_only_a_guess() -> None:
    handler = _handler(_registered())
    request = _request(token="whatever", token_type_hint="saml2_token")

    answer = await handler.respond_to_request(request, Response())

    assert await _body(answer) == {"active": False}
