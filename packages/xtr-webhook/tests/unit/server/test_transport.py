from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_client import MockHttpClient, MockResponse
from xtr_http_client_contracts import TransportError
from xtr_remote_event import RemoteEvent

from tests.support.fake_request_configurator import FakeRequestConfigurator
from xtr_webhook.exception import DeliveryError, LogicError
from xtr_webhook.server import OutgoingRequest, Transport
from xtr_webhook.subscriber import Subscriber

if TYPE_CHECKING:
    from xtr_http_client_contracts import HttpClientInterface

pytestmark = pytest.mark.anyio

_URL = "https://receiver.test/hook"


def _event() -> RemoteEvent:
    return RemoteEvent(name="order.created", id="evt_1", payload={"total": 10})


def _subscriber() -> Subscriber:
    return Subscriber(_URL, "s3cr3t")


def _transport(
    client: HttpClientInterface | None = None,
    headers: FakeRequestConfigurator | None = None,
    body: FakeRequestConfigurator | None = None,
    signer: FakeRequestConfigurator | None = None,
) -> Transport:
    return Transport(
        client=client if client is not None else MockHttpClient(),
        headers=headers or FakeRequestConfigurator(),
        body=body or FakeRequestConfigurator(write=_writes_body),
        signer=signer or FakeRequestConfigurator(),
    )


def _writes_body(request: OutgoingRequest) -> None:
    request.body = b'{"total":10}'


def _answering(status_code: int) -> MockHttpClient:
    return MockHttpClient(MockResponse(info={"http_code": status_code}))


async def test_it_runs_headers_then_body_then_signer() -> None:
    order: list[str] = []

    def _writes_body_in_order(request: OutgoingRequest) -> None:
        order.append("body")
        _writes_body(request)

    transport = _transport(
        headers=FakeRequestConfigurator(write=lambda _: order.append("headers")),
        body=FakeRequestConfigurator(write=_writes_body_in_order),
        signer=FakeRequestConfigurator(write=lambda _: order.append("signer")),
    )

    await transport.send(_subscriber(), _event())

    assert order == ["headers", "body", "signer"]


async def test_every_configurator_shares_one_fresh_request() -> None:
    headers = FakeRequestConfigurator()
    body = FakeRequestConfigurator(write=_writes_body)
    signer = FakeRequestConfigurator()
    transport = _transport(headers=headers, body=body, signer=signer)

    await transport.send(_subscriber(), _event())

    request = headers.calls[0][2]
    assert body.calls[0][2] is request
    assert signer.calls[0][2] is request


async def test_each_send_builds_a_request_of_its_own() -> None:
    headers = FakeRequestConfigurator()
    transport = _transport(headers=headers)

    await transport.send(_subscriber(), _event())
    await transport.send(_subscriber(), _event())

    assert headers.calls[0][2] is not headers.calls[1][2]


async def test_every_configurator_is_handed_the_event_and_the_secret() -> None:
    headers = FakeRequestConfigurator()
    signer = FakeRequestConfigurator()
    event = _event()
    transport = _transport(headers=headers, signer=signer)

    await transport.send(_subscriber(), event)

    assert headers.calls[0][:2] == (event, "s3cr3t")
    assert signer.calls[0][:2] == (event, "s3cr3t")


async def test_it_posts_the_url_the_headers_and_the_body_the_chain_built() -> None:
    answer = MockResponse()

    def _writes_everything(request: OutgoingRequest) -> None:
        request.headers["Webhook-Id"] = "evt_1"
        request.headers["Webhook-Signature"] = "sha256=abc"
        request.body = b'{"total":10}'

    transport = _transport(
        MockHttpClient(answer), body=FakeRequestConfigurator(write=_writes_everything)
    )

    await transport.send(_subscriber(), _event())

    sent = answer.get_request_options()
    assert answer.get_request_method() == "POST"
    assert answer.get_request_url() == _URL
    assert sent["headers"] == {"Webhook-Id": "evt_1", "Webhook-Signature": "sha256=abc"}
    assert sent["body"] == b'{"total":10}'


async def test_it_asks_the_client_to_follow_no_redirect() -> None:
    answer = MockResponse()

    await _transport(MockHttpClient(answer)).send(_subscriber(), _event())

    assert answer.get_request_options()["max_redirects"] == 0


async def test_it_leaves_the_timeout_to_the_client() -> None:
    answer = MockResponse()
    client = MockHttpClient(answer).with_options(timeout=7.5)

    await _transport(client).send(_subscriber(), _event())

    assert answer.get_request_options()["timeout"] == 7.5


@pytest.mark.parametrize("status_code", [200, 202, 299])
async def test_an_answer_inside_2xx_is_a_delivery(status_code: int) -> None:
    client = _answering(status_code)

    await _transport(client).send(_subscriber(), _event())

    assert client.get_requests_count() == 1


@pytest.mark.parametrize("status_code", [199, 300, 302, 404, 500])
async def test_an_answer_outside_2xx_raises_a_delivery_error(status_code: int) -> None:
    transport = _transport(_answering(status_code))

    with pytest.raises(DeliveryError) as caught:
        await transport.send(_subscriber(), _event())

    assert caught.value.status_code == status_code
    assert caught.value.url == _URL


async def test_a_refused_delivery_says_what_came_back() -> None:
    transport = _transport(_answering(500))

    with pytest.raises(
        DeliveryError,
        match=r'^The webhook to "https://receiver\.test/hook" was answered with HTTP 500\.$',
    ):
        await transport.send(_subscriber(), _event())


async def test_a_delivery_nothing_answered_raises_the_clients_own_error() -> None:
    transport = _transport(MockHttpClient(MockResponse(info={"error": "Connection refused."})))

    with pytest.raises(TransportError, match=r"^Connection refused\.$"):
        await transport.send(_subscriber(), _event())


async def test_a_chain_that_never_wrote_a_body_is_refused_before_posting() -> None:
    client = MockHttpClient()
    transport = _transport(client, body=FakeRequestConfigurator())

    with pytest.raises(LogicError, match=r"^The body must be set\.$"):
        await transport.send(_subscriber(), _event())

    assert client.get_requests_count() == 0
