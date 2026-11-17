"""Where a refusal from the authorization endpoint is delivered, and what it says."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, final
from urllib.parse import parse_qs, urlsplit

import pytest
from typing_extensions import override
from xtr_clock import MockClock
from xtr_http_kernel.bridge import Response
from xtr_security import Security
from xtr_security_oauth2_server_core.grant.abstract_grant import AbstractGrant
from xtr_security_oauth2_server_core.request_types.authorization_request import AuthorizationRequest

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entity_builders import client_entity, scope_entities
from tests.support.grants import Storage
from tests.support.messages import MultiValuedForm, document_of, server_request
from tests.support.recording_logger import RecordingLogger
from tests.support.servers import make_server
from tests.support.signing import ISSUER
from xtr_security_oauth2_server.controller.authorization_controller import (
    AuthorizationController,
    _answered_at,
)
from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.converter.user_converter import UserConverter
from xtr_security_oauth2_server.event.authorization_request_resolve_event_factory import (
    AuthorizationRequestResolveEventFactory,
)
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_oauth2_server_core.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

pytestmark = pytest.mark.anyio

_NOW: Final = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
_REDIRECT_URI: Final = "https://client.test/callback"
_STATE: Final = "the-opaque-state"
_CLIENT_ID: Final = "client-1"
_FLOW: Final = "authorization_code"

#: What a browser asking for a code sends, in the order it sends it.
_ASKING: Final = (
    ("response_type", "code"),
    ("client_id", _CLIENT_ID),
    ("redirect_uri", _REDIRECT_URI),
    ("state", _STATE),
)


def _request(
    redirect_uri: str | None = _REDIRECT_URI,
    state: str | None = _STATE,
) -> AuthorizationRequest:
    """Return an authorization request naming what a client sent."""
    built = AuthorizationRequest()
    built.set_client(client_entity())
    built.set_redirect_uri(redirect_uri)
    if state is not None:
        built.set_state(state)

    return built


@final
class _AuthorizeGrant(AbstractGrant):
    """The redirect flow, as far as the endpoint needs one: it reads a request."""

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        scopes: tuple[str, ...] = (),
    ) -> None:
        super().__init__(dispatcher, clock)
        self._asked_for = scopes

    @override
    def get_identifier(self) -> str:
        return _FLOW

    @override
    def can_respond_to_authorization_request(self, request: ServerRequestInterface) -> bool:
        return request.get_query_params().get("response_type") == "code"

    @override
    async def validate_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> AuthorizationRequestInterface:
        del request
        built = _request()
        built.set_grant_type_id(self.get_identifier())
        built.set_scopes(scope_entities(*self._asked_for))

        return built

    @override
    async def complete_authorization_request(
        self,
        request: ServerRequestInterface,
        authorization_request: AuthorizationRequestInterface,
    ) -> ResponseTypeInterface:
        del request, authorization_request

        raise AssertionError("nobody approved anything here")  # pragma: no cover

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        del request, response_type, access_token_ttl

        raise AssertionError("no token is asked for here")  # pragma: no cover


def _controller(
    logger: RecordingLogger | None = None,
    clients: ClientManager | None = None,
    asked_for: tuple[str, ...] = (),
) -> AuthorizationController:
    """Return the endpoint over a server running the redirect flow and nobody signed in."""
    dispatcher = RecordingEventDispatcher()
    clients = ClientManager(dispatcher) if clients is None else clients
    clock = MockClock(_NOW)
    server = make_server(Storage(), dispatcher, clock)
    server.enable_grant_type(_AuthorizeGrant(dispatcher, clock, asked_for))

    return AuthorizationController(
        server,
        dispatcher,
        AuthorizationRequestResolveEventFactory(ScopeConverter(), clients),
        UserConverter(),
        clients,
        Security(_NoToken(), _NoDecision()),
        logger,
    )


async def _registered_for(*scopes: str) -> ClientManager:
    """Return a client store holding the requesting client, registered for ``scopes``."""
    clients = ClientManager(RecordingEventDispatcher())
    await clients.save(
        Client("Test client", _CLIENT_ID, None).set_scopes(*(Scope(name) for name in scopes))
    )

    return clients


def _sent_back_with(answered: Response) -> dict[str, list[str]]:
    """Return what a redirect sends the browser back to the client with."""
    assert answered.get_status_code() == 302

    return parse_qs(urlsplit(answered.get_header_line("location")).query)


async def test_a_scope_the_client_is_not_registered_for_is_refused_before_anyone_is_asked() -> None:
    # The resource owner would otherwise be shown a consent page for a scope
    # the token can never carry.
    logger = RecordingLogger()
    controller = _controller(logger, await _registered_for("read"), asked_for=("write",))

    sent = _sent_back_with(await controller.index_action(_asking_for_a_code(), Response(200)))

    assert sent["error"] == ["invalid_scope"]
    assert sent["state"] == [_STATE]
    assert logger.messages("warning") == []


async def test_a_scope_the_client_is_registered_for_goes_on_to_the_resource_owner() -> None:
    controller = _controller(clients=await _registered_for("read"), asked_for=("read",))

    sent = _sent_back_with(await controller.index_action(_asking_for_a_code(), Response(200)))

    assert sent["error"] == ["access_denied"]


async def test_a_client_registered_for_no_scope_may_ask_for_any() -> None:
    controller = _controller(clients=await _registered_for(), asked_for=("write",))

    sent = _sent_back_with(await controller.index_action(_asking_for_a_code(), Response(200)))

    assert sent["error"] == ["access_denied"]


async def test_a_refusal_the_endpoint_makes_names_the_server_that_sent_it() -> None:
    # RFC 9207: every authorization response, a refusal too, carries ``iss``.
    sent = _sent_back_with(await _controller().index_action(_asking_for_a_code(), Response(200)))

    assert sent["iss"] == [ISSUER]


def _asking_for_a_code() -> ServerRequestInterface:
    """Return the request a browser arrives with, carrying nobody authenticated."""
    return server_request(
        "GET",
        "/authorize",
        query_params=dict(_ASKING),
    )


def test_a_refusal_goes_to_the_redirect_uri_carrying_the_state() -> None:
    # RFC 6749 4.1.2.1: a client that cannot tie an error back to the request
    # it made cannot tell it from a forged redirect.
    assert _answered_at(_request()) == f"{_REDIRECT_URI}?state={_STATE}"


def test_a_request_that_sent_no_state_is_answered_at_the_bare_uri() -> None:
    # A client reads ``state=`` as state it never sent.
    assert _answered_at(_request(state=None)) == _REDIRECT_URI


def test_a_request_naming_no_redirect_uri_has_nowhere_safe_to_be_answered() -> None:
    assert _answered_at(_request(redirect_uri=None)) is None


async def test_nobody_to_ask_is_logged_with_the_step_the_deployment_is_missing() -> None:
    # The client is told nothing about how this deployment is put together, so
    # the one place the mistake can be seen is the server's own log.
    logger = RecordingLogger()

    _ = await _controller(logger).index_action(_asking_for_a_code(), Response(200))

    warned = logger.messages("warning")
    assert len(warned) == 1
    assert "firewall claiming the authorization endpoint" in warned[0]
    assert "Use in an application" in warned[0]


async def test_the_warning_carries_the_client_and_the_flow_as_data() -> None:
    logger = RecordingLogger()

    _ = await _controller(logger).index_action(_asking_for_a_code(), Response(200))

    assert logger.contexts("warning") == [{"client_id": _CLIENT_ID, "grant_type": _FLOW}]


async def test_the_client_is_still_told_only_that_consent_was_refused() -> None:
    logger = RecordingLogger()

    answered = await _controller(logger).index_action(_asking_for_a_code(), Response(200))

    delivered = answered.get_header_line("location")
    assert "error=access_denied" in delivered
    assert f"state={_STATE}" in delivered
    assert "firewall" not in delivered.lower()


async def test_a_deployment_logging_nothing_answers_the_client_just_the_same() -> None:
    # Logging is a peer this package does without: an application that lists no
    # logging bundle still gets the refusal delivered.
    answered = await _controller().index_action(_asking_for_a_code(), Response(200))

    assert answered.get_status_code() == 302


async def test_a_request_posted_as_a_form_is_read_as_its_query_would_be() -> None:
    posted = server_request(
        "POST",
        "/authorize",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        parsed_body=MultiValuedForm(_ASKING),
    )

    answered = await _controller().index_action(posted, Response(200))

    assert "error=access_denied" in answered.get_header_line("location")


async def test_a_request_posted_as_no_form_is_refused_as_a_document() -> None:
    posted = server_request("POST", "/authorize", headers={"Content-Type": "application/json"})

    answered = await _controller().index_action(posted, Response(200))

    assert answered.get_status_code() == 400
    assert answered.get_header_line("location") == ""
    document = await document_of(answered)
    assert isinstance(document, dict)
    assert document["error"] == "invalid_request"


def test_it_names_the_type_and_nothing_it_holds() -> None:
    # It holds the server, the dispatcher and the firewall's per-request
    # service, none of which a reader of a log line needs.
    storage = Storage()
    dispatcher = RecordingEventDispatcher()
    clients = ClientManager(dispatcher)
    controller = AuthorizationController(
        make_server(storage, dispatcher, MockClock(_NOW)),
        dispatcher,
        AuthorizationRequestResolveEventFactory(ScopeConverter(), clients),
        UserConverter(),
        clients,
        Security(_NoToken(), _NoDecision()),
    )

    assert repr(controller) == "AuthorizationController()"


class _NoToken:
    """Token storage with nobody authenticated, as an unclaimed request has."""

    def get_token(self) -> None:
        return None

    def set_token(self, token: object | None = None) -> None:
        del token

        raise AssertionError("nothing authenticates here")  # pragma: no cover


class _NoDecision:
    """An authorization checker nothing asks."""

    async def is_granted(
        self,
        attribute: object,
        subject: object = None,
        access_decision: object = None,
    ) -> bool:
        del attribute, subject, access_decision

        raise AssertionError("nothing is checked here")  # pragma: no cover
