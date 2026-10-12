"""Where a refusal from the authorization endpoint is delivered, and what it says."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, final

import pytest
from typing_extensions import override
from xtr_clock import MockClock
from xtr_http_kernel.bridge import Response
from xtr_security import Security

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entity_builders import client_entity
from tests.support.grants import Storage
from tests.support.messages import server_request
from tests.support.recording_logger import RecordingLogger
from tests.support.servers import make_server
from xtr_security_oauth2_server.controller.authorization_controller import (
    AuthorizationController,
    _answered_at,
)
from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.converter.user_converter import UserConverter
from xtr_security_oauth2_server.event.authorization_request_resolve_event_factory import (
    AuthorizationRequestResolveEventFactory,
)
from xtr_security_oauth2_server.grant.abstract_grant import AbstractGrant
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager
from xtr_security_oauth2_server.request_types.authorization_request import AuthorizationRequest

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )
    from xtr_security_oauth2_server.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

pytestmark = pytest.mark.anyio

_NOW: Final = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
_REDIRECT_URI: Final = "https://client.test/callback"
_STATE: Final = "the-opaque-state"
_CLIENT_ID: Final = "client-1"
_FLOW: Final = "authorization_code"


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


def _controller(logger: RecordingLogger | None = None) -> AuthorizationController:
    """Return the endpoint over a server running the redirect flow and nobody signed in."""
    dispatcher = RecordingEventDispatcher()
    clients = ClientManager(dispatcher)
    clock = MockClock(_NOW)
    server = make_server(Storage(), dispatcher, clock)
    server.enable_grant_type(_AuthorizeGrant(dispatcher, clock))

    return AuthorizationController(
        server,
        dispatcher,
        AuthorizationRequestResolveEventFactory(ScopeConverter(), clients),
        UserConverter(),
        clients,
        Security(_NoToken(), _NoDecision()),
        logger,
    )


def _asking_for_a_code() -> ServerRequestInterface:
    """Return the request a browser arrives with, carrying nobody authenticated."""
    return server_request(
        "GET",
        "/authorize",
        query_params={
            "response_type": "code",
            "client_id": _CLIENT_ID,
            "redirect_uri": _REDIRECT_URI,
            "state": _STATE,
        },
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
    assert "Firewall()" in warned[0]
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
