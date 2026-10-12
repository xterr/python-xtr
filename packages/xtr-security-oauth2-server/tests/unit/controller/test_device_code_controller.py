"""The endpoint a device asks for its pair of codes at, enabled and not."""

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
from xtr_security_oauth2_server.controller.device_code_controller import DeviceCodeController

pytestmark = pytest.mark.anyio

_NOW: Final = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
_NOT_FOUND: Final = 404


def _controller(*, enabled: bool) -> DeviceCodeController:
    """Return the endpoint over a server running no device flow."""
    server = make_server(Storage(), RecordingEventDispatcher(), MockClock(_NOW))

    return DeviceCodeController(server, enabled)


async def test_a_deployment_that_did_not_enable_the_flow_answers_not_found() -> None:
    # The route exists either way: the router is built when the package is
    # imported and cannot know a deployment's configuration.
    answered = await _controller(enabled=False).index_action(
        server_request("POST", "/device-code"),
        Response(200),
    )

    assert answered.get_status_code() == _NOT_FOUND


async def test_a_refusal_from_the_server_is_answered_as_the_refusal_it_is() -> None:
    # Nothing enabled the device grant on the server, so there is no flow to
    # answer the request — which is the endpoint's own error branch.
    answered = await _controller(enabled=True).index_action(
        server_request("POST", "/device-code", parsed_body={"client_id": "a-client"}),
        Response(200),
    )

    assert answered.get_status_code() != _NOT_FOUND
    document = document_of(answered)
    assert isinstance(document, dict)
    assert document["error"] == "unsupported_grant_type"


def test_it_says_whether_the_flow_is_enabled_and_nothing_else() -> None:
    assert repr(_controller(enabled=True)) == "DeviceCodeController(enabled=True)"
