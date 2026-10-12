"""Reading the token a client handed over, as either of the kinds this server issues."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.encryption import seal
from tests.support.entities import make_client
from tests.support.grants import Storage
from tests.support.handlers import wire_handler
from tests.support.messages import server_request
from tests.support.signing import FROZEN_NOW, ISSUER, make_clock
from tests.support.tokens import sealed_refresh_token, signed_access_token
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.handlers.abstract_token_handler import AbstractTokenHandler
from xtr_security_oauth2_server_core.handlers.token_handler_interface import TokenHandlerInterface
from xtr_security_oauth2_server_core.handlers.validated_token import ValidatedToken

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

_A_MONTH = timedelta(days=30)


@final
class _Handler(AbstractTokenHandler):
    """A handler that answers nothing, so the reading alone is exercised."""

    @override
    async def respond_to_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        del request

        return response


@final
class _RecordingValidator:
    """A reading of an access token that accepts anything, and says what it was asked."""

    def __init__(self, claims: Mapping[str, object]) -> None:
        self.claims: Mapping[str, object] = claims
        self.asked: list[tuple[ServerRequestInterface, str]] = []

    async def validate_bearer_token(
        self,
        request: ServerRequestInterface,
        token: str,
    ) -> Mapping[str, object]:
        """Record what was asked, and answer the claims this was built with."""
        self.asked.append((request, token))

        return self.claims


def _request(**body: str) -> ServerRequestInterface:
    return server_request(
        "POST",
        "https://authorization.example.com/revoke",
        parsed_body=dict(body),
    )


def _handler(storage: Storage | None = None) -> tuple[_Handler, Storage]:
    held = storage if storage is not None else Storage()
    handler = _Handler(RecordingEventDispatcher(), make_clock())
    wire_handler(handler, held)

    return (handler, held)


def test_it_declares_the_contract_the_token_server_drives_it_through() -> None:
    assert TokenHandlerInterface in AbstractTokenHandler.__mro__


@pytest.mark.anyio
async def test_the_validator_it_was_given_is_what_reads_an_access_token() -> None:
    handler, _ = _handler()
    validator = _RecordingValidator({"foo": "bar"})
    handler.set_bearer_token_validator(validator)
    request = _request(token="abcdef")

    read = await handler.validate_token(request, make_client("client-1"))

    assert read == ValidatedToken("access_token", {"foo": "bar"})
    assert validator.asked == [(request, "abcdef")]


@pytest.mark.anyio
async def test_a_handler_never_told_what_reads_an_access_token_names_the_setter() -> None:
    handler = _Handler(RecordingEventDispatcher(), make_clock())
    handler.set_client_repository(Storage().clients)

    with pytest.raises(InvalidArgumentError, match="set_bearer_token_validator"):
        _ = await handler.validate_token(_request(token="abcdef"), make_client("client-1"))


@pytest.mark.anyio
async def test_a_request_naming_no_token_is_refused() -> None:
    handler, _ = _handler()

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.validate_token(_request(), make_client("client-1"))

    assert refusal.value.get_error_type() == "invalid_request"
    assert "token" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_an_access_token_is_read_as_what_it_claims() -> None:
    handler, _ = _handler()

    read = await handler.validate_token(
        _request(token=signed_access_token()),
        make_client("client-1"),
    )

    assert read is not None
    assert read.token_type == "access_token"
    assert read.token_data["jti"] == "access-1"
    assert read.token_data["client_id"] == "client-1"
    assert read.token_data["sub"] == "user-1"
    assert read.token_data["scope"] == "read"
    assert read.token_data["iss"] == ISSUER
    assert read.token_data["exp"] == int((FROZEN_NOW + timedelta(hours=1)).timestamp())


@pytest.mark.anyio
async def test_a_revoked_access_token_is_read_as_nothing() -> None:
    handler, storage = _handler()
    await storage.access_tokens.revoke_access_token("access-1")

    read = await handler.validate_token(
        _request(token=signed_access_token()),
        make_client("client-1"),
    )

    assert read is None


@pytest.mark.anyio
async def test_an_expired_access_token_is_read_as_nothing() -> None:
    handler, _ = _handler()
    token = signed_access_token(lifetime=timedelta(seconds=-1))

    read = await handler.validate_token(_request(token=token), make_client("client-1"))

    assert read is None


@pytest.mark.anyio
async def test_another_clients_access_token_is_still_read_for_what_it_says() -> None:
    handler, _ = _handler()
    token = signed_access_token(client_id="client-2")

    read = await handler.validate_token(_request(token=token), make_client("client-1"))

    assert read is not None
    assert read.token_type == "access_token"
    assert read.token_data["client_id"] == "client-2"


@pytest.mark.anyio
async def test_something_that_is_not_a_token_is_read_as_nothing() -> None:
    handler, _ = _handler()

    read = await handler.validate_token(_request(token="abcdef"), make_client("client-1"))

    assert read is None


@pytest.mark.anyio
async def test_a_refresh_token_is_read_as_the_payload_it_was_sealed_from() -> None:
    handler, _ = _handler()
    sealed = seal(
        {
            "refresh_token_id": "refresh-1",
            "expire_time": int((FROZEN_NOW + _A_MONTH).timestamp()),
            "client_id": "client-1",
            "foo": "bar",
        },
    )

    read = await handler.validate_token(_request(token=sealed), make_client("client-1"))

    assert read == ValidatedToken(
        "refresh_token",
        {
            "refresh_token_id": "refresh-1",
            "expire_time": int((FROZEN_NOW + _A_MONTH).timestamp()),
            "client_id": "client-1",
            "foo": "bar",
        },
    )


@pytest.mark.anyio
async def test_a_revoked_refresh_token_is_read_as_nothing() -> None:
    handler, storage = _handler()
    _ = await storage.refresh_tokens.revoke_refresh_token("refresh-1")

    read = await handler.validate_token(
        _request(token=sealed_refresh_token()),
        make_client("client-1"),
    )

    assert read is None


@pytest.mark.anyio
async def test_an_expired_refresh_token_is_read_as_nothing() -> None:
    handler, _ = _handler()
    token = sealed_refresh_token(lifetime=timedelta(seconds=-1))

    read = await handler.validate_token(_request(token=token), make_client("client-1"))

    assert read is None


@pytest.mark.anyio
async def test_another_clients_refresh_token_is_read_as_nothing() -> None:
    handler, _ = _handler()
    token = sealed_refresh_token(client_id="client-2")

    read = await handler.validate_token(_request(token=token), make_client("client-1"))

    assert read is None


@pytest.mark.anyio
async def test_the_kind_a_client_guesses_at_only_decides_which_reading_comes_first() -> None:
    handler, _ = _handler()
    request = _request(token=signed_access_token(), token_type_hint="refresh_token")

    read = await handler.validate_token(request, make_client("client-1"))

    assert read is not None
    assert read.token_type == "access_token"
