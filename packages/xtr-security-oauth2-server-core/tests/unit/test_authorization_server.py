"""The server every endpoint goes through: grants, tokens, revocation, answers."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final, Literal, cast, final

import pytest
from typing_extensions import override
from xtr_http_message import Response

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.encryption import ENCRYPTION_KEY
from tests.support.entities import DeviceCode, make_client
from tests.support.grants import Storage
from tests.support.messages import MultiValuedForm, document_of, server_request
from tests.support.response_types import RecordingResponseType
from tests.support.servers import make_server
from tests.support.signing import FROZEN_NOW, make_clock
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.grant.abstract_grant import AbstractGrant
from xtr_security_oauth2_server_core.grant.client_credentials_grant import ClientCredentialsGrant
from xtr_security_oauth2_server_core.request_types.authorization_request import AuthorizationRequest
from xtr_security_oauth2_server_core.response_types.bearer_token_response import BearerTokenResponse
from xtr_security_oauth2_server_core.response_types.device_code_response import DeviceCodeResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer
    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )
    from xtr_security_oauth2_server_core.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

_AN_HOUR: Final[timedelta] = timedelta(hours=1)
_A_MONTH: Final[timedelta] = timedelta(days=30)
_DEVICE_GRANT: Final[str] = "urn:ietf:params:oauth:grant-type:device_code"
_CALLBACK: Final[str] = "https://client.example.com/callback"


@final
class _LocationResponseType:
    """A response type whose whole answer is a redirect."""

    def set_access_token(self, access_token: AccessTokenEntityInterface) -> None:
        del access_token

    def set_refresh_token(self, refresh_token: RefreshTokenEntityInterface) -> None:
        del refresh_token

    def set_encryption_key(self, key: str, key_type: Literal["plain", "key"]) -> None:
        del key, key_type

    def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        return response.with_status(302).with_header("Location", f"{_CALLBACK}?code=abc")


@final
class _StubGrant(AbstractGrant):
    """A grant that answers by name, keeping what it was handed."""

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        identifier: str = "stub",
    ) -> None:
        super().__init__(dispatcher, clock)
        self.identifier: str = identifier
        self.handed: list[ResponseTypeInterface] = []
        self.ttls: list[timedelta] = []

    @override
    def get_identifier(self) -> str:
        return self.identifier

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        del request
        self.handed.append(response_type)
        self.ttls.append(access_token_ttl)

        return response_type


@final
class _AuthorizeGrant(AbstractGrant):
    """A grant that answers authorization requests asking for a code."""

    @override
    def get_identifier(self) -> str:
        return "authorization_code"

    @override
    def can_respond_to_authorization_request(self, request: ServerRequestInterface) -> bool:
        return request.get_query_params().get("response_type") == "code"

    @override
    async def validate_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> AuthorizationRequestInterface:
        del request
        authorization_request = AuthorizationRequest()
        authorization_request.set_grant_type_id(self.get_identifier())
        authorization_request.set_client(make_client())

        return authorization_request

    @override
    async def complete_authorization_request(
        self,
        request: ServerRequestInterface,
        authorization_request: AuthorizationRequestInterface,
    ) -> ResponseTypeInterface:
        del request, authorization_request

        return _LocationResponseType()

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        del request, access_token_ttl

        return response_type


@final
class _DeviceGrant(AbstractGrant):
    """A grant that issues the two codes a device polls with."""

    def __init__(self, dispatcher: EventDispatcherInterface, clock: ClockInterface) -> None:
        super().__init__(dispatcher, clock)
        self.completed: tuple[str, str, bool] | None = None

    @override
    def get_identifier(self) -> str:
        return _DEVICE_GRANT

    @override
    def can_respond_to_device_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> bool:
        del request

        return True

    @override
    async def respond_to_device_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> DeviceCodeResponse:
        del request
        device_code = DeviceCode()
        device_code.set_identifier("device-1")
        device_code.set_user_code("BCDFGHJK")
        device_code.set_verification_uri("https://authorization.example.com/device")
        device_code.set_expiry_date_time(FROZEN_NOW + timedelta(minutes=10))
        device_code.set_interval(5)
        device_code.set_client(make_client())
        answer = DeviceCodeResponse(self._clock)
        answer.set_device_code_entity(device_code)

        return answer

    @override
    async def complete_device_authorization_request(
        self,
        device_code: str,
        user_id: str,
        user_approved: bool,
    ) -> None:
        self.completed = (device_code, user_id, user_approved)

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        del request, access_token_ttl

        return response_type


def _token_request(grant_type: str = "stub", **body: str) -> ServerRequestInterface:
    return server_request(
        "POST",
        "https://authorization.example.com/token",
        parsed_body={"grant_type": grant_type, **body},
    )


def _authorize_request(**query: str) -> ServerRequestInterface:
    return server_request(
        "GET",
        "https://authorization.example.com/authorize",
        query_params=query,
    )


def _endpoint_request(**body: str) -> ServerRequestInterface:
    return server_request(
        "POST",
        "https://authorization.example.com/revoke",
        parsed_body={"client_id": "client-1", "client_secret": "secret", **body},
    )


def _registered(storage: Storage) -> Storage:
    storage.clients.add(make_client("client-1"), "secret")

    return storage


def _body(answer: ResponseInterface) -> Mapping[str, object]:
    return cast("Mapping[str, object]", document_of(answer))


def _server(
    storage: Storage | None = None,
    response_type: ResponseTypeInterface | None = None,
) -> AuthorizationServer:
    return make_server(
        storage if storage is not None else Storage(),
        RecordingEventDispatcher(),
        make_clock(),
        response_type,
    )


def _stub(server: AuthorizationServer, identifier: str = "stub") -> _StubGrant:
    grant = _StubGrant(RecordingEventDispatcher(), make_clock(), identifier)
    server.enable_grant_type(grant)

    return grant


def test_enabling_a_grant_hands_it_everything_the_server_holds() -> None:
    storage = Storage()
    server = _server(storage)

    grant = _stub(server)

    assert grant._client_repository is storage.clients
    assert grant._access_token_repository is storage.access_tokens
    assert grant._scope_repository is storage.scopes
    assert grant._default_scope == ""
    assert grant._private_key is not None


def test_a_grant_is_handed_the_default_scope_set_before_it_was_enabled() -> None:
    server = _server()
    server.set_default_scope("read")

    assert _stub(server)._default_scope == "read"


def test_a_grant_is_handed_the_refresh_token_policy_set_before_it_was_enabled() -> None:
    server = _server()
    server.revoke_refresh_tokens(False)

    assert _stub(server)._revoke_refresh_tokens is False


@pytest.mark.anyio
async def test_a_grant_enabled_without_a_lifetime_issues_tokens_for_an_hour() -> None:
    server = _server(response_type=RecordingResponseType())
    grant = _stub(server)

    _ = await server.respond_to_access_token_request(_token_request(), Response())

    assert grant.ttls == [_AN_HOUR]


@pytest.mark.anyio
async def test_the_lifetime_a_grant_was_enabled_with_is_the_one_it_is_given() -> None:
    server = _server(response_type=RecordingResponseType())
    grant = _StubGrant(RecordingEventDispatcher(), make_clock())
    server.enable_grant_type(grant, timedelta(minutes=5))

    _ = await server.respond_to_access_token_request(_token_request(), Response())

    assert grant.ttls == [timedelta(minutes=5)]


@pytest.mark.anyio
async def test_the_token_request_is_answered_by_the_grant_it_names() -> None:
    server = _server(response_type=RecordingResponseType())
    first = _stub(server, "first")
    second = _stub(server, "second")

    _ = await server.respond_to_access_token_request(_token_request("second"), Response())

    assert first.handed == []
    assert len(second.handed) == 1


@pytest.mark.anyio
async def test_a_token_request_no_grant_answers_is_refused() -> None:
    server = _server()
    _ = _stub(server)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await server.respond_to_access_token_request(_token_request("password"), Response())

    assert refusal.value.get_error_type() == "unsupported_grant_type"


@pytest.mark.anyio
async def test_a_token_request_repeating_the_grant_type_is_refused() -> None:
    # RFC 6749 section 3.2: a parameter may not be included more than once,
    # and section 5.2 catalogues a request that repeats one under
    # ``invalid_request``. The grant chooses nothing, so the name it is chosen
    # by is judged before it is offered the request.
    server = _server(response_type=RecordingResponseType())
    grant = _stub(server)
    repeated = MultiValuedForm([("grant_type", "stub"), ("grant_type", "stub")])

    with pytest.raises(OAuthServerError) as refusal:
        _ = await server.respond_to_access_token_request(
            server_request("POST", "/token", parsed_body=repeated),
            Response(),
        )

    assert refusal.value.get_error_type() == "invalid_request"
    assert "grant_type" in str(refusal.value.get_hint())
    assert grant.handed == []


@pytest.mark.anyio
async def test_a_token_request_naming_two_grant_types_reaches_neither() -> None:
    # The reason the name is judged first: reading the last value sent would
    # let one hop append a grant type the client never asked for and have this
    # server run it.
    server = _server(response_type=RecordingResponseType())
    asked_for = _stub(server, "first")
    appended = _stub(server, "second")
    repeated = MultiValuedForm([("grant_type", "first"), ("grant_type", "second")])

    with pytest.raises(OAuthServerError) as refusal:
        _ = await server.respond_to_access_token_request(
            server_request("POST", "/token", parsed_body=repeated),
            Response(),
        )

    assert refusal.value.get_error_type() == "invalid_request"
    assert asked_for.handed == []
    assert appended.handed == []


@pytest.mark.anyio
async def test_the_answer_is_built_on_the_response_the_caller_handed_in() -> None:
    # The server builds no response of its own: whoever is serving the request
    # owns what the answer starts out as.
    server = _server(response_type=RecordingResponseType())
    _ = _stub(server)
    response = Response(headers={"x-trace": "1"})

    answer = await server.respond_to_access_token_request(_token_request(), response)

    assert answer.get_header_line("x-trace") == "1"


@pytest.mark.anyio
async def test_each_token_request_is_answered_by_its_own_response_type() -> None:
    server = _server(response_type=RecordingResponseType())
    grant = _stub(server)

    _ = await server.respond_to_access_token_request(_token_request(), Response())
    _ = await server.respond_to_access_token_request(_token_request(), Response())

    first, second = grant.handed
    assert first is not second


@pytest.mark.anyio
async def test_two_token_requests_do_not_share_the_token_they_earned() -> None:
    storage = _registered(Storage())
    server = _server(storage, BearerTokenResponse(make_clock()))
    server.enable_grant_type(ClientCredentialsGrant(RecordingEventDispatcher(), make_clock()))
    request = _token_request("client_credentials", client_id="client-1", client_secret="secret")

    first = await server.respond_to_access_token_request(request, Response())
    second = await server.respond_to_access_token_request(request, Response())

    assert _body(first)["access_token"] != _body(second)["access_token"]


@pytest.mark.anyio
async def test_the_response_type_a_grant_is_handed_can_seal_its_own_payloads() -> None:
    server = _server(response_type=RecordingResponseType())
    grant = _stub(server)

    _ = await server.respond_to_access_token_request(_token_request(), Response())

    assert cast("RecordingResponseType", grant.handed[0]).encryption_key == (
        ENCRYPTION_KEY,
        "key",
    )


@pytest.mark.anyio
async def test_the_response_type_it_was_built_with_is_left_untouched() -> None:
    template = RecordingResponseType()
    server = _server(response_type=template)
    _ = _stub(server)

    _ = await server.respond_to_access_token_request(_token_request(), Response())

    assert template.encryption_key is None


@pytest.mark.anyio
async def test_a_server_built_with_no_response_type_hands_out_bearer_tokens() -> None:
    storage = _registered(Storage())
    server = _server(storage)
    server.enable_grant_type(ClientCredentialsGrant(RecordingEventDispatcher(), make_clock()))
    request = _token_request("client_credentials", client_id="client-1", client_secret="secret")

    answer = await server.respond_to_access_token_request(request, Response())

    assert _body(answer)["token_type"] == "Bearer"


@pytest.mark.anyio
async def test_an_authorization_request_naming_no_response_type_is_refused() -> None:
    server = _server()
    _ = _stub(server)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await server.validate_authorization_request(_authorize_request(client_id="client-1"))

    assert refusal.value.get_error_type() == "invalid_request"
    assert "response_type" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_an_authorization_request_repeating_the_response_type_is_refused() -> None:
    # The same sentence of RFC 6749 section 3.1, for the parameter that
    # decides which flow reads an authorization request.
    server = _server()
    server.enable_grant_type(_AuthorizeGrant(RecordingEventDispatcher(), make_clock()))
    repeated = MultiValuedForm([("response_type", "code"), ("response_type", "code")])

    with pytest.raises(OAuthServerError) as refusal:
        _ = await server.validate_authorization_request(
            server_request("GET", "/authorize", query_params=repeated),
        )

    assert refusal.value.get_error_type() == "invalid_request"
    assert "response_type" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_an_authorization_request_is_read_by_the_grant_that_can() -> None:
    server = _server()
    server.enable_grant_type(_AuthorizeGrant(RecordingEventDispatcher(), make_clock()))

    read = await server.validate_authorization_request(_authorize_request(response_type="code"))

    assert read.get_grant_type_id() == "authorization_code"


@pytest.mark.anyio
async def test_an_authorization_request_no_grant_answers_is_refused() -> None:
    server = _server()
    server.enable_grant_type(_AuthorizeGrant(RecordingEventDispatcher(), make_clock()))

    with pytest.raises(OAuthServerError) as refusal:
        _ = await server.validate_authorization_request(_authorize_request(response_type="token"))

    assert refusal.value.get_error_type() == "unsupported_grant_type"


@pytest.mark.anyio
async def test_completing_an_authorization_request_answers_the_grants_redirect() -> None:
    server = _server()
    server.enable_grant_type(_AuthorizeGrant(RecordingEventDispatcher(), make_clock()))
    request = _authorize_request(response_type="code")
    read = await server.validate_authorization_request(request)

    answer = await server.complete_authorization_request(request, read, Response())

    assert answer.get_status_code() == 302
    assert answer.get_header_line("location") == f"{_CALLBACK}?code=abc"


@pytest.mark.anyio
async def test_completing_a_request_for_a_grant_that_is_not_enabled_names_it() -> None:
    server = _server()
    read = AuthorizationRequest()
    read.set_grant_type_id("implicit")
    read.set_client(make_client())

    with pytest.raises(InvalidArgumentError, match="implicit"):
        _ = await server.complete_authorization_request(_authorize_request(), read, Response())


@pytest.mark.anyio
async def test_a_device_authorization_request_is_answered_by_the_device_grant() -> None:
    server = _server()
    server.enable_grant_type(_DeviceGrant(RecordingEventDispatcher(), make_clock()))

    answer = await server.respond_to_device_authorization_request(
        _endpoint_request(),
        Response(),
    )

    assert _body(answer)["user_code"] == "BCDFGHJK"


@pytest.mark.anyio
async def test_a_device_authorization_request_no_grant_answers_is_refused() -> None:
    server = _server()
    _ = _stub(server)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await server.respond_to_device_authorization_request(
            _endpoint_request(),
            Response(),
        )

    assert refusal.value.get_error_type() == "unsupported_grant_type"


@pytest.mark.anyio
async def test_a_decision_about_a_device_code_reaches_the_device_grant() -> None:
    server = _server()
    grant = _DeviceGrant(RecordingEventDispatcher(), make_clock())
    server.enable_grant_type(grant)

    await server.complete_device_authorization_request(
        "device-1",
        "user-1",
        True,
    )

    assert grant.completed == ("device-1", "user-1", True)


@pytest.mark.anyio
async def test_a_decision_about_a_device_code_without_the_device_grant_names_it() -> None:
    server = _server()

    with pytest.raises(InvalidArgumentError, match="device_code"):
        await server.complete_device_authorization_request(
            "device-1",
            "user-1",
            True,
        )


def test_its_reading_says_a_key_is_held_and_never_which() -> None:
    shown = repr(_server())

    assert "AuthorizationServer" in shown
    assert ENCRYPTION_KEY not in shown
