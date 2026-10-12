"""The server the two endpoints about a token a client already holds go through."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast, final

import pytest
from xtr_http_message import Response

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.encryption import ENCRYPTION_KEY
from tests.support.entities import make_client
from tests.support.grants import Storage
from tests.support.messages import body_of, document_of, server_request
from tests.support.servers import make_token_server
from tests.support.signing import ISSUER, make_clock
from tests.support.tokens import sealed_refresh_token, signed_access_token
from xtr_security_oauth2_server_core.authorization_validators.bearer_token_validator import (
    BearerTokenValidator,
)
from xtr_security_oauth2_server_core.handlers.token_handler_interface import TokenHandlerInterface
from xtr_security_oauth2_server_core.handlers.token_introspection_handler import (
    TokenIntrospectionHandler,
)
from xtr_security_oauth2_server_core.handlers.token_revocation_handler import TokenRevocationHandler

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_oauth2_server_core.authorization_validators import (
        BearerTokenValidatorInterface,
    )
    from xtr_security_oauth2_server_core.repositories.access_token_repository_interface import (
        AccessTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
        ClientRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.token_server import TokenServer


@final
class _RecordingHandler:
    """A handler that answers a marked response, and keeps what it was handed."""

    def __init__(self) -> None:
        self.asked: list[ServerRequestInterface] = []
        self.clients: ClientRepositoryInterface | None = None
        self.access_tokens: AccessTokenRepositoryInterface | None = None
        self.refresh_tokens: RefreshTokenRepositoryInterface | None = None
        self.validator: BearerTokenValidatorInterface | None = None
        self.encryption_key: tuple[str, Literal["plain", "key"]] | None = None

    async def respond_to_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        """Keep the request, and answer a response nothing else would produce."""
        self.asked.append(request)
        answer = response.with_status(299)
        _ = answer.get_body().write(b"answered")

        return answer

    def set_client_repository(self, client_repository: ClientRepositoryInterface) -> None:
        """Keep the repository registered clients would be read from."""
        self.clients = client_repository

    def set_access_token_repository(
        self,
        access_token_repository: AccessTokenRepositoryInterface,
    ) -> None:
        """Keep the repository access tokens would be withdrawn through."""
        self.access_tokens = access_token_repository

    def set_refresh_token_repository(
        self,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> None:
        """Keep the repository refresh tokens would be withdrawn through."""
        self.refresh_tokens = refresh_token_repository

    def set_bearer_token_validator(
        self,
        bearer_token_validator: BearerTokenValidatorInterface,
    ) -> None:
        """Keep what the access tokens it is handed would be read by."""
        self.validator = bearer_token_validator

    def set_encryption_key(self, key: str, key_type: Literal["plain", "key"]) -> None:
        """Keep the key the refresh tokens it reads were sealed with."""
        self.encryption_key = (key, key_type)


@final
class _AppRevocationHandler(TokenRevocationHandler):
    """The withdrawal a deployment installs: ours, subclassed and nothing more."""


@final
class _AppIntrospectionHandler(TokenIntrospectionHandler):
    """The question a deployment installs: ours, subclassed and nothing more."""


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


def _server(storage: Storage | None = None) -> TokenServer:
    return make_token_server(
        storage if storage is not None else _registered(),
        RecordingEventDispatcher(),
        make_clock(),
    )


def _installed_withdrawal() -> _AppRevocationHandler:
    return _AppRevocationHandler(RecordingEventDispatcher(), make_clock())


def _installed_question() -> _AppIntrospectionHandler:
    return _AppIntrospectionHandler(RecordingEventDispatcher(), make_clock())


def _body(answer: ResponseInterface) -> Mapping[str, object]:
    return cast("Mapping[str, object]", document_of(answer))


def test_the_recording_handler_satisfies_the_handler_contract() -> None:
    assert isinstance(_RecordingHandler(), TokenHandlerInterface)


@pytest.mark.anyio
async def test_a_revocation_request_is_answered_without_a_word() -> None:
    answer = await _server().respond_to_token_revocation_request(
        _request(token="whatever"),
        Response(),
    )

    assert answer.get_status_code() == 200
    assert body_of(answer) == ""
    assert answer.get_header_line("cache-control") == "no-store"


@pytest.mark.anyio
async def test_an_introspection_request_about_an_unknown_token_says_nothing_is_live() -> None:
    answer = await _server().respond_to_token_introspection_request(
        _request(token="whatever"),
        Response(),
    )

    assert answer.get_status_code() == 200
    assert answer.get_header_line("content-type") == "application/json; charset=UTF-8"
    assert _body(answer) == {"active": False}


@pytest.mark.anyio
async def test_the_answer_is_built_on_the_response_the_caller_handed_in() -> None:
    # Neither endpoint builds a response of its own: whoever is serving the
    # request owns what the answer starts out as.
    answer = await _server().respond_to_token_revocation_request(
        _request(token="whatever"),
        Response(headers={"x-trace": "1"}),
    )

    assert answer.get_header_line("x-trace") == "1"


@pytest.mark.anyio
async def test_the_revocation_handler_it_was_given_is_the_one_that_answers() -> None:
    server = _server()
    handler = _RecordingHandler()
    server.set_token_revocation_handler(handler)
    request = _request(token="whatever")

    answer = await server.respond_to_token_revocation_request(request, Response())

    assert answer.get_status_code() == 299
    assert body_of(answer) == "answered"
    assert handler.asked == [request]


@pytest.mark.anyio
async def test_the_introspection_handler_it_was_given_is_the_one_that_answers() -> None:
    server = _server()
    handler = _RecordingHandler()
    server.set_token_introspection_handler(handler)
    request = _request(token="whatever")

    answer = await server.respond_to_token_introspection_request(request, Response())

    assert answer.get_status_code() == 299
    assert body_of(answer) == "answered"
    assert handler.asked == [request]


@pytest.mark.anyio
async def test_a_handler_it_was_given_is_handed_the_stores_and_the_key() -> None:
    storage = _registered()
    server = _server(storage)
    handler = _RecordingHandler()
    server.set_token_revocation_handler(handler)

    _ = await server.respond_to_token_revocation_request(_request(token="whatever"), Response())

    assert handler.clients is storage.clients
    assert handler.access_tokens is storage.access_tokens
    assert handler.refresh_tokens is storage.refresh_tokens
    assert handler.encryption_key == (ENCRYPTION_KEY, "key")


@pytest.mark.anyio
async def test_a_handler_it_was_given_is_handed_what_reads_an_access_token() -> None:
    server = _server()
    revocation = _RecordingHandler()
    introspection = _RecordingHandler()
    server.set_token_revocation_handler(revocation)
    server.set_token_introspection_handler(introspection)

    _ = await server.respond_to_token_revocation_request(_request(token="whatever"), Response())
    _ = await server.respond_to_token_introspection_request(_request(token="whatever"), Response())

    assert isinstance(revocation.validator, BearerTokenValidator)
    assert introspection.validator is revocation.validator


@pytest.mark.anyio
async def test_an_access_token_is_withdrawn_through_the_server() -> None:
    storage = _registered()
    server = _server(storage)

    answer = await server.respond_to_token_revocation_request(
        _request(token=signed_access_token()),
        Response(),
    )

    assert answer.get_status_code() == 200
    assert await storage.access_tokens.is_access_token_revoked("access-1")


@pytest.mark.anyio
async def test_a_refresh_token_is_answered_for_through_the_server() -> None:
    server = _server()

    answer = await server.respond_to_token_introspection_request(
        _request(token=sealed_refresh_token()),
        Response(),
    )

    body = _body(answer)
    assert body["active"] is True
    assert body["jti"] == "refresh-1"


@pytest.mark.anyio
async def test_a_question_a_deployment_installed_answers_for_a_live_token() -> None:
    server = _server()
    server.set_token_introspection_handler(_installed_question())

    answer = await server.respond_to_token_introspection_request(
        _request(token=signed_access_token()),
        Response(),
    )

    body = _body(answer)
    assert body["active"] is True
    assert body["jti"] == "access-1"


@pytest.mark.anyio
async def test_a_withdrawal_a_deployment_installed_leaves_nothing_for_the_question() -> None:
    storage = _registered()
    server = _server(storage)
    server.set_token_revocation_handler(_installed_withdrawal())
    server.set_token_introspection_handler(_installed_question())
    token = signed_access_token()

    withdrawn = await server.respond_to_token_revocation_request(
        _request(token=token),
        Response(),
    )
    answer = await server.respond_to_token_introspection_request(
        _request(token=token),
        Response(),
    )

    assert withdrawn.get_status_code() == 200
    assert await storage.access_tokens.is_access_token_revoked("access-1")
    assert _body(answer) == {"active": False}


@pytest.mark.anyio
async def test_each_endpoint_keeps_its_own_handler() -> None:
    server = _server()
    revocation = _RecordingHandler()
    server.set_token_revocation_handler(revocation)

    answer = await server.respond_to_token_introspection_request(
        _request(token="whatever"),
        Response(),
    )

    assert revocation.asked == []
    assert _body(answer) == {"active": False}


def test_its_reading_names_what_it_answers_for_and_never_the_keys() -> None:
    shown = repr(_server())

    assert shown == f"TokenServer(issuer={ISSUER!r}, audience=None)"
    assert ENCRYPTION_KEY not in shown
