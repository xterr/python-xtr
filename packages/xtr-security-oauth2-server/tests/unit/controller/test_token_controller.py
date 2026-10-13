"""The endpoint every flow but one ends at, and the answer it announces."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

import pytest
from xtr_clock import MockClock
from xtr_http_kernel.bridge import Response

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.grants import Storage
from tests.support.messages import document_of, server_request
from tests.support.servers import make_server
from xtr_security_oauth2_server.controller.token_controller import TokenController
from xtr_security_oauth2_server.event.token_request_resolve_event import TokenRequestResolveEvent
from xtr_security_oauth2_server.oauth2_events import OAuth2Events

pytestmark = pytest.mark.anyio

_NOW: Final = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def _controller(dispatcher: RecordingEventDispatcher) -> TokenController:
    """Return the endpoint over a server running no flow at all."""
    return TokenController(
        make_server(Storage(), dispatcher, MockClock(_NOW)),
        dispatcher,
    )


async def test_a_grant_type_no_enabled_flow_answers_is_refused() -> None:
    answered = await _controller(RecordingEventDispatcher()).index_action(
        server_request(parsed_body={"grant_type": "client_credentials"}),
        Response(200),
    )

    document = await document_of(answered)
    assert isinstance(document, dict)
    assert document["error"] == "unsupported_grant_type"


async def test_a_refusal_is_announced_as_an_answer_like_any_other() -> None:
    # A deployment counting failed exchanges wants to see them, and one adding
    # a field of its own adds it in a listener rather than by replacing this.
    dispatcher = RecordingEventDispatcher()

    _ = await _controller(dispatcher).index_action(
        server_request(parsed_body={"grant_type": "client_credentials"}),
        Response(200),
    )

    assert OAuth2Events.TOKEN_REQUEST_RESOLVE in dispatcher.names()


async def test_the_answer_a_listener_put_on_the_event_is_what_is_sent() -> None:
    dispatcher = RecordingEventDispatcher()
    replacement = Response(418)

    def replace(event: object) -> None:
        assert isinstance(event, TokenRequestResolveEvent)
        _ = event.set_response(replacement)

    dispatcher.listen(OAuth2Events.TOKEN_REQUEST_RESOLVE, replace)

    answered = await _controller(dispatcher).index_action(
        server_request(parsed_body={"grant_type": "client_credentials"}),
        Response(200),
    )

    assert answered is replacement


def test_it_names_the_type_and_nothing_it_holds() -> None:
    assert repr(_controller(RecordingEventDispatcher())) == "TokenController()"
