"""The endpoint something asks what this server says about a token at."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

import pytest
from xtr_clock import MockClock
from xtr_http_kernel.bridge import Response

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.grants import Storage
from tests.support.messages import document_of, server_request
from tests.support.servers import make_token_server
from xtr_security_oauth2_server.controller.introspection_controller import (
    IntrospectionController,
)

pytestmark = pytest.mark.anyio

_NOW: Final = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
_NOT_FOUND: Final = 404


def _controller(*, enabled: bool) -> IntrospectionController:
    """Return the endpoint over a token server with nothing registered."""
    server = make_token_server(Storage(), RecordingEventDispatcher(), MockClock(_NOW))

    return IntrospectionController(server, enabled)


async def test_a_deployment_that_did_not_enable_it_answers_not_found() -> None:
    # Off by default: it answers questions about tokens issued to *other*
    # clients, so a deployment turns it on deliberately.
    answered = await _controller(enabled=False).index_action(
        server_request("POST", "/introspect"),
        Response(200),
    )

    assert answered.get_status_code() == _NOT_FOUND


async def test_a_request_naming_no_client_is_refused() -> None:
    answered = await _controller(enabled=True).index_action(
        server_request("POST", "/introspect", parsed_body={"token": "whatever"}),
        Response(200),
    )

    document = document_of(answered)
    assert isinstance(document, dict)
    assert document["error"] == "invalid_request"


def test_it_says_whether_the_endpoint_is_enabled_and_nothing_else() -> None:
    assert repr(_controller(enabled=True)) == "IntrospectionController(enabled=True)"
