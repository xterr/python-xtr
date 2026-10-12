"""What a grant and a token handler share: reading the request, and proving the client."""

from __future__ import annotations

import base64
from collections.abc import Iterator, Mapping, Sequence
from datetime import timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.encryption import ENCRYPTION_KEY, seal
from tests.support.entities import make_client
from tests.support.grants import Storage, wire
from tests.support.messages import server_request
from tests.support.signing import FROZEN_NOW, make_clock
from xtr_security_oauth2_server.abstract_handler import AbstractHandler
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.grant.client_credentials_grant import ClientCredentialsGrant
from xtr_security_oauth2_server.request_event import RequestEvent

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface

_A_MONTH = timedelta(days=30)


@final
class _Form(Mapping[str, str]):
    """A submitted form as a web framework hands one over.

    Nothing may change it, and a field sent more than once reads as the last
    value — which is what reading a form field by name means everywhere.
    """

    def __init__(self, fields: Sequence[tuple[str, str]]) -> None:
        self._fields: tuple[tuple[str, str], ...] = tuple(fields)

    @override
    def __getitem__(self, key: str) -> str:
        for name, value in reversed(self._fields):
            if name == key:
                return value

        raise KeyError(key)

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(dict(self._fields))

    @override
    def __len__(self) -> int:
        return len(dict(self._fields))


@final
class _Handler(AbstractHandler):
    """A handler that is no flow, so the request is read without one."""


@final
class _RecordingClientRepository:
    """A client repository that remembers which flow it was asked about."""

    def __init__(
        self,
        client: ClientEntityInterface | None,
        secret: str = "secret",  # noqa: S107 -- the secret the one client registered with
    ) -> None:
        self._client: ClientEntityInterface | None = client
        self._secret: str = secret
        self.asked: list[str | None] = []

    async def get_client_entity(self, client_identifier: str) -> ClientEntityInterface | None:
        """Return the one client this was built with, when it is the one asked for."""
        if self._client is None or self._client.get_identifier() != client_identifier:
            return None

        return self._client

    async def validate_client(
        self,
        client_identifier: str,
        client_secret: str | None,
        grant_type: str | None,
    ) -> bool:
        """Record the flow, and answer whether the secret is the registered one."""
        del client_identifier
        self.asked.append(grant_type)

        return client_secret == self._secret


def _request(**body: str) -> ServerRequestInterface:
    return server_request(
        "POST",
        "https://authorization.example.com/revoke",
        parsed_body={"client_id": "client-1", "client_secret": "secret", **body},
    )


def _basic(client_id: str, secret: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{client_id}:{secret}".encode()).decode("ascii")

    return {"Authorization": f"Basic {encoded}"}


def _handler(
    repository: _RecordingClientRepository | None = None,
    storage: Storage | None = None,
) -> _Handler:
    held = storage if storage is not None else Storage()
    handler = _Handler(RecordingEventDispatcher(), make_clock())
    handler.set_client_repository(
        repository if repository is not None else _RecordingClientRepository(make_client()),
    )
    handler.set_access_token_repository(held.access_tokens)
    handler.set_refresh_token_repository(held.refresh_tokens)
    handler.set_encryption_key(ENCRYPTION_KEY, "key")

    return handler


@pytest.mark.anyio
async def test_a_handler_that_is_no_flow_names_no_flow_to_the_repository() -> None:
    repository = _RecordingClientRepository(make_client())
    handler = _handler(repository)

    client = await handler.validate_client(_request())

    assert client.get_identifier() == "client-1"
    assert repository.asked == [None]


@pytest.mark.anyio
async def test_a_grant_names_itself_to_the_repository() -> None:
    repository = _RecordingClientRepository(make_client())
    storage = Storage()
    grant = ClientCredentialsGrant(RecordingEventDispatcher(), make_clock())
    wire(grant, storage)
    grant.set_client_repository(repository)

    _ = await grant.validate_client(_request())

    assert repository.asked == ["client_credentials"]


@pytest.mark.anyio
async def test_a_request_naming_no_client_is_refused() -> None:
    handler = _handler()
    request = server_request("POST", "/revoke", parsed_body={})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.validate_client(request)

    assert refusal.value.get_error_type() == "invalid_request"
    assert "client_id" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_confidential_client_sending_no_secret_is_told_what_is_missing() -> None:
    handler = _handler()
    request = server_request("POST", "/revoke", parsed_body={"client_id": "client-1"})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.validate_client(request)

    assert refusal.value.get_error_type() == "invalid_request"
    assert "client_secret" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_public_client_is_asked_for_no_secret() -> None:
    repository = _RecordingClientRepository(make_client(confidential=False))
    handler = _handler(repository)

    client = await handler.validate_client(
        server_request("POST", "/revoke", parsed_body={"client_id": "client-1"}),
    )

    assert client.get_identifier() == "client-1"
    assert repository.asked == []


@pytest.mark.anyio
async def test_a_client_nobody_registered_is_a_failed_authentication() -> None:
    dispatcher = RecordingEventDispatcher()
    handler = _Handler(dispatcher, make_clock())
    handler.set_client_repository(_RecordingClientRepository(None))

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.validate_client(_request())

    assert refusal.value.get_error_type() == "invalid_client"
    assert dispatcher.only().name == RequestEvent.CLIENT_AUTHENTICATION_FAILED


@pytest.mark.anyio
async def test_a_wrong_secret_is_a_failed_authentication() -> None:
    dispatcher = RecordingEventDispatcher()
    handler = _Handler(dispatcher, make_clock())
    handler.set_client_repository(_RecordingClientRepository(make_client()))

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.validate_client(_request(client_secret="wrong"))

    assert refusal.value.get_error_type() == "invalid_client"
    assert dispatcher.only().name == RequestEvent.CLIENT_AUTHENTICATION_FAILED


def test_the_credentials_may_come_from_the_basic_header() -> None:
    handler = _handler()
    request = server_request("POST", "/revoke", headers=_basic("client-1", "secret"))

    assert handler.get_client_credentials(request) == ("client-1", "secret")


def test_a_request_with_no_body_at_all_carries_no_parameter() -> None:
    handler = _handler()

    request = server_request("POST", "/revoke")

    assert request.get_parsed_body() is None
    assert handler.get_request_parameter("token", request) is None


def test_a_body_that_parsed_into_no_parameters_carries_none() -> None:
    handler = _handler()

    # A JSON array parses into structure that is not named parameters, which
    # is as good as no parameter at all.
    request = server_request("POST", "/revoke", parsed_body=["token", "abc"])

    assert handler.get_request_parameter("token", request) is None


def test_a_form_nothing_may_change_is_read_as_it_is() -> None:
    handler = _handler()
    # What a web framework hands over is its own immutable form object; it is
    # read rather than copied, so a parameter still comes out of it.
    form = MappingProxyType({"client_id": "client-1", "token": "abc"})

    request = server_request("POST", "/revoke", parsed_body=form)

    assert handler.get_request_parameter("token", request) == "abc"


def test_a_form_field_sent_twice_reads_as_the_last_value() -> None:
    handler = _handler()
    form = _Form([("token", "first"), ("token", "last")])

    request = server_request("POST", "/revoke", parsed_body=form)

    assert handler.get_request_parameter("token", request) == "last"


def test_a_parameter_carried_as_something_other_than_text_is_refused() -> None:
    handler = _handler()
    request = server_request("POST", "/revoke", parsed_body={"token": ["a", "b"]})

    with pytest.raises(OAuthServerError) as refusal:
        _ = handler.get_request_parameter("token", request)

    assert refusal.value.get_error_type() == "invalid_request"
    assert "token" in str(refusal.value.get_hint())


def test_a_query_parameter_is_read_off_the_query() -> None:
    handler = _handler()
    request = server_request("GET", "/authorize", query_params={"client_id": "client-1"})

    assert handler.get_query_string_parameter("client_id", request) == "client-1"


def test_a_cookie_is_read_off_the_cookies() -> None:
    handler = _handler()
    request = server_request("POST", "/revoke", cookie_params={"session": "s-1"})

    assert handler.get_cookie_parameter("session", request) == "s-1"


def test_a_cookie_nobody_sent_reads_as_the_default() -> None:
    handler = _handler()
    request = server_request("POST", "/revoke")

    assert handler.get_cookie_parameter("session", request, "none") == "none"
    assert handler.get_cookie_parameter("session", request) is None


def test_an_environment_parameter_is_read_off_the_environment() -> None:
    handler = _handler()
    request = server_request("POST", "/revoke", server_params={"REMOTE_ADDR": "10.0.0.1"})

    assert handler.get_server_parameter("REMOTE_ADDR", request) == "10.0.0.1"


def test_an_environment_parameter_that_is_not_text_is_refused() -> None:
    handler = _handler()
    request = server_request("POST", "/revoke", server_params={"SERVER_PORT": 443})

    with pytest.raises(OAuthServerError) as refusal:
        _ = handler.get_server_parameter("SERVER_PORT", request)

    assert refusal.value.get_error_type() == "invalid_request"


def test_a_handler_never_told_where_clients_are_read_from_names_the_setter() -> None:
    handler = _Handler(RecordingEventDispatcher(), make_clock())

    with pytest.raises(InvalidArgumentError, match="set_client_repository"):
        _ = handler._client_repository_or_fail()


@pytest.mark.anyio
async def test_a_refresh_token_sealed_here_is_opened_into_its_payload() -> None:
    handler = _handler()
    payload: dict[str, object] = {
        "client_id": "client-1",
        "refresh_token_id": "refresh-1",
        "access_token_id": "access-1",
        "expire_time": int((FROZEN_NOW + _A_MONTH).timestamp()),
        "foo": "bar",
    }

    read = await handler.validate_encrypted_refresh_token(_request(), seal(payload), "client-1")

    assert read == payload


@pytest.mark.anyio
async def test_a_refresh_token_this_server_did_not_seal_is_refused() -> None:
    handler = _handler()

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.validate_encrypted_refresh_token(_request(), "abcdef", "client-1")

    assert refusal.value.get_error_type() == "invalid_grant"
    assert refusal.value.get_hint() == "Cannot decrypt the refresh token"


@pytest.mark.anyio
async def test_a_refresh_token_of_another_client_is_refused_and_announced() -> None:
    dispatcher = RecordingEventDispatcher()
    handler = _Handler(dispatcher, make_clock())
    handler.set_encryption_key(ENCRYPTION_KEY, "key")
    sealed = seal(
        {
            "client_id": "client-2",
            "refresh_token_id": "refresh-1",
            "expire_time": int((FROZEN_NOW + _A_MONTH).timestamp()),
        },
    )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.validate_encrypted_refresh_token(_request(), sealed, "client-1")

    assert refusal.value.get_hint() == "Token is not linked to client"
    assert dispatcher.only().name == RequestEvent.REFRESH_TOKEN_CLIENT_FAILED


@pytest.mark.anyio
async def test_an_expired_refresh_token_is_refused() -> None:
    handler = _handler()
    sealed = seal(
        {
            "client_id": "client-1",
            "refresh_token_id": "refresh-1",
            "expire_time": int(FROZEN_NOW.timestamp()) - 1,
        },
    )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.validate_encrypted_refresh_token(_request(), sealed, "client-1")

    assert refusal.value.get_hint() == "Token has expired"


@pytest.mark.anyio
async def test_a_refresh_token_payload_naming_no_token_is_refused() -> None:
    handler = _handler()
    sealed = seal(
        {"client_id": "client-1", "expire_time": int((FROZEN_NOW + _A_MONTH).timestamp())},
    )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.validate_encrypted_refresh_token(_request(), sealed, "client-1")

    assert refusal.value.get_hint() == "Token is malformed"


@pytest.mark.anyio
async def test_a_revoked_refresh_token_is_refused() -> None:
    storage = Storage()
    _ = await storage.refresh_tokens.revoke_refresh_token("refresh-1")
    handler = _handler(storage=storage)
    sealed = seal(
        {
            "client_id": "client-1",
            "refresh_token_id": "refresh-1",
            "expire_time": int((FROZEN_NOW + _A_MONTH).timestamp()),
        },
    )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await handler.validate_encrypted_refresh_token(_request(), sealed, "client-1")

    assert refusal.value.get_hint() == "Token has been revoked"


@pytest.mark.anyio
async def test_a_handler_asked_about_a_refresh_token_with_no_store_names_the_setter() -> None:
    handler = _Handler(RecordingEventDispatcher(), make_clock())
    handler.set_encryption_key(ENCRYPTION_KEY, "key")
    sealed = seal(
        {
            "client_id": "client-1",
            "refresh_token_id": "refresh-1",
            "expire_time": int((FROZEN_NOW + _A_MONTH).timestamp()),
        },
    )

    with pytest.raises(InvalidArgumentError, match="set_refresh_token_repository"):
        _ = await handler.validate_encrypted_refresh_token(_request(), sealed, "client-1")


def test_its_reading_says_a_key_is_held_and_never_which() -> None:
    handler = _handler()

    shown = repr(handler)

    assert shown == "<_Handler encryption_key=set>"
    assert ENCRYPTION_KEY not in shown
