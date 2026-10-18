"""The channel listener redirects a request onto the scheme its matched rule demands."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from starlette.responses import Response as StarletteResponse
from xtr_http_kernel import RequestEvent
from xtr_http_kernel.bridge import Response as DualResponse
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_http_message import HttpFactory

from tests.support.messages import make_message
from tests.support.recording_logger import RecordingLogger
from xtr_security_http.firewall.channel_listener import ChannelListener
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_http_message_contracts.factory import ResponseFactoryInterface

pytestmark = pytest.mark.anyio


@final
class _ChannelMap:
    """Answers what it was built with, recording every request it was asked."""

    def __init__(
        self, channel: str | None, *, attributes: tuple[str, ...] = ("ROLE_USER",)
    ) -> None:
        self._answer = (attributes, channel)
        self.asked: list[ServerRequestInterface] = []

    async def get_patterns(
        self, request: ServerRequestInterface
    ) -> tuple[tuple[str, ...], str | None]:
        """Record the ask, and answer the patterns this map was built with."""
        self.asked.append(request)
        return self._answer


def _listener(
    access_map: _ChannelMap,
    *,
    logger: RecordingLogger | None = None,
    http_port: int = 80,
    https_port: int = 443,
    responses: ResponseFactoryInterface | None = None,
) -> ChannelListener:
    """Build the step over a map answering one canned channel."""
    return ChannelListener(
        access_map,
        responses if responses is not None else ResponseFactory(),
        StarletteHttpFactory(),
        logger=logger,
        http_port=http_port,
        https_port=https_port,
    )


async def _redirect_of(
    listener: ChannelListener, request: ServerRequestInterface
) -> StarletteResponse:
    """Run the step over ``request`` and return the response it answered with."""
    if await listener.supports(request) is False:
        raise AssertionError("the step skipped a request it was expected to answer")
    event = RequestEvent(request, {})
    await listener.authenticate(event)
    response = event.response
    assert response is not None
    return response


def test_it_satisfies_the_interface() -> None:
    assert isinstance(_listener(_ChannelMap("https")), FirewallListenerInterface)


def test_its_priority_is_the_chains_default() -> None:
    assert ChannelListener.get_priority() == 0


async def test_supports_asks_the_map_about_the_request() -> None:
    access_map = _ChannelMap("https")
    request = make_message(scheme="http")

    _ = await _listener(access_map).supports(request)

    assert access_map.asked == [request]


async def test_supports_answers_true_when_https_is_demanded_of_a_plain_request() -> None:
    answer = await _listener(_ChannelMap("https")).supports(make_message(scheme="http"))

    assert answer is True


async def test_supports_answers_true_when_http_is_demanded_of_an_encrypted_request() -> None:
    answer = await _listener(_ChannelMap("http")).supports(make_message())

    assert answer is True


async def test_supports_answers_false_when_the_matched_rule_demands_no_channel() -> None:
    answer = await _listener(_ChannelMap(None)).supports(make_message(scheme="http"))

    assert answer is False


async def test_supports_answers_false_when_no_rule_matches() -> None:
    answer = await _listener(_ChannelMap(None, attributes=())).supports(make_message(scheme="http"))

    assert answer is False


async def test_supports_answers_false_when_the_request_already_arrived_over_https() -> None:
    answer = await _listener(_ChannelMap("https")).supports(make_message())

    assert answer is False


async def test_supports_answers_false_when_the_request_already_arrived_over_http() -> None:
    answer = await _listener(_ChannelMap("http")).supports(make_message(scheme="http"))

    assert answer is False


async def test_the_redirect_to_https_names_no_port_by_default() -> None:
    response = await _redirect_of(
        _listener(_ChannelMap("https")), make_message(scheme="http", path="/admin")
    )

    assert response.headers["location"] == "https://example.com/admin"


async def test_the_redirect_to_http_names_no_port_by_default() -> None:
    response = await _redirect_of(_listener(_ChannelMap("http")), make_message(path="/admin"))

    assert response.headers["location"] == "http://example.com/admin"


async def test_the_redirect_to_https_spells_out_a_custom_https_port() -> None:
    response = await _redirect_of(
        _listener(_ChannelMap("https"), https_port=8443),
        make_message(scheme="http", path="/admin"),
    )

    assert response.headers["location"] == "https://example.com:8443/admin"


async def test_the_redirect_to_http_spells_out_a_custom_http_port() -> None:
    response = await _redirect_of(
        _listener(_ChannelMap("http"), http_port=8080),
        make_message(path="/admin"),
    )

    assert response.headers["location"] == "http://example.com:8080/admin"


async def test_a_custom_http_port_is_not_spelled_out_on_a_redirect_to_https() -> None:
    response = await _redirect_of(
        _listener(_ChannelMap("https"), http_port=8080),
        make_message(scheme="http", path="/admin"),
    )

    assert response.headers["location"] == "https://example.com/admin"


async def test_a_custom_https_port_is_not_spelled_out_on_a_redirect_to_http() -> None:
    response = await _redirect_of(
        _listener(_ChannelMap("http"), https_port=8443),
        make_message(path="/admin"),
    )

    assert response.headers["location"] == "http://example.com/admin"


async def test_the_redirect_leaves_the_port_the_request_arrived_on_behind() -> None:
    response = await _redirect_of(
        _listener(_ChannelMap("https")),
        make_message(scheme="http", host="example.com:8080", path="/admin"),
    )

    assert response.headers["location"] == "https://example.com/admin"


async def test_the_redirect_keeps_the_path_and_its_query_string() -> None:
    response = await _redirect_of(
        _listener(_ChannelMap("https")),
        make_message(scheme="http", path="/admin/books", query="page=2&filter=old"),
    )

    assert response.headers["location"] == "https://example.com/admin/books?page=2&filter=old"


async def test_authenticate_answers_with_a_301_redirect() -> None:
    response = await _redirect_of(
        _listener(_ChannelMap("https")), make_message(scheme="http", path="/admin")
    )

    assert response.status_code == 301
    assert response.headers["location"] == "https://example.com/admin"


async def test_authenticate_sends_a_kernel_response_as_it_is() -> None:
    response = await _redirect_of(
        _listener(_ChannelMap("https")), make_message(scheme="http", path="/admin")
    )

    assert isinstance(response, DualResponse)


async def test_authenticate_bridges_a_pure_message_response() -> None:
    response = await _redirect_of(
        _listener(_ChannelMap("https"), responses=HttpFactory()),
        make_message(scheme="http", path="/admin"),
    )

    assert isinstance(response, StarletteResponse)
    assert not isinstance(response, DualResponse)
    assert response.status_code == 301
    assert response.headers["location"] == "https://example.com/admin"


async def test_a_redirect_to_https_is_logged() -> None:
    logger = RecordingLogger()

    _ = await _listener(_ChannelMap("https"), logger=logger).supports(make_message(scheme="http"))

    assert logger.messages("info") == ["Redirecting to HTTPS."]


async def test_a_redirect_to_https_behind_a_forwarded_proto_header_names_the_header() -> None:
    logger = RecordingLogger()
    request = make_message(scheme="http", headers={"X-Forwarded-Proto": "https"})

    _ = await _listener(_ChannelMap("https"), logger=logger).supports(request)

    (message,) = logger.messages("info")
    assert message.startswith("Redirecting to HTTPS.")
    assert "X-Forwarded-Proto" in message


async def test_a_redirect_to_https_behind_a_forwarded_header_names_the_proto() -> None:
    logger = RecordingLogger()
    request = make_message(scheme="http", headers={"Forwarded": "for=1.2.3.4;proto=https"})

    _ = await _listener(_ChannelMap("https"), logger=logger).supports(request)

    (message,) = logger.messages("info")
    assert message.startswith("Redirecting to HTTPS.")
    assert "proto=https" in message


async def test_a_redirect_to_http_is_logged() -> None:
    logger = RecordingLogger()

    _ = await _listener(_ChannelMap("http"), logger=logger).supports(make_message())

    assert logger.messages("info") == ["Redirecting to HTTP."]


async def test_a_request_already_on_the_demanded_scheme_writes_no_log() -> None:
    logger = RecordingLogger()

    _ = await _listener(_ChannelMap("https"), logger=logger).supports(make_message())

    assert logger.records == []
