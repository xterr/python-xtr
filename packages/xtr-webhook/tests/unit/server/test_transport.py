from __future__ import annotations

import pytest
from xtr_remote_event import RemoteEvent

from tests.support.fake_http_sender import FakeHttpSender
from tests.support.fake_request_configurator import FakeRequestConfigurator
from xtr_webhook.exception import DeliveryError, LogicError
from xtr_webhook.server import OutgoingRequest, Transport
from xtr_webhook.subscriber import Subscriber

pytestmark = pytest.mark.anyio


def _event() -> RemoteEvent:
    return RemoteEvent(name="order.created", id="evt_1", payload={"total": 10})


def _subscriber() -> Subscriber:
    return Subscriber("https://receiver.test/hook", "s3cr3t")


def _transport(
    sender: FakeHttpSender,
    headers: FakeRequestConfigurator | None = None,
    body: FakeRequestConfigurator | None = None,
    signer: FakeRequestConfigurator | None = None,
) -> Transport:
    return Transport(
        sender=sender,
        headers=headers or FakeRequestConfigurator(),
        body=body or FakeRequestConfigurator(write=_writes_body),
        signer=signer or FakeRequestConfigurator(),
    )


def _writes_body(request: OutgoingRequest) -> None:
    request.body = b'{"total":10}'


async def test_it_runs_headers_then_body_then_signer() -> None:
    order: list[str] = []
    sender = FakeHttpSender()

    def _writes_body_in_order(request: OutgoingRequest) -> None:
        order.append("body")
        _writes_body(request)

    transport = _transport(
        sender,
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
    transport = _transport(FakeHttpSender(), headers=headers, body=body, signer=signer)

    await transport.send(_subscriber(), _event())

    request = headers.calls[0][2]
    assert body.calls[0][2] is request
    assert signer.calls[0][2] is request


async def test_each_send_builds_a_request_of_its_own() -> None:
    headers = FakeRequestConfigurator()
    transport = _transport(FakeHttpSender(), headers=headers)

    await transport.send(_subscriber(), _event())
    await transport.send(_subscriber(), _event())

    assert headers.calls[0][2] is not headers.calls[1][2]


async def test_every_configurator_is_handed_the_event_and_the_secret() -> None:
    headers = FakeRequestConfigurator()
    signer = FakeRequestConfigurator()
    event = _event()
    transport = _transport(FakeHttpSender(), headers=headers, signer=signer)

    await transport.send(_subscriber(), event)

    assert headers.calls[0][:2] == (event, "s3cr3t")
    assert signer.calls[0][:2] == (event, "s3cr3t")


async def test_it_posts_the_url_the_headers_and_the_body_the_chain_built() -> None:
    sender = FakeHttpSender()

    def _writes_everything(request: OutgoingRequest) -> None:
        request.headers["Webhook-Id"] = "evt_1"
        request.body = b'{"total":10}'

    transport = _transport(sender, body=FakeRequestConfigurator(write=_writes_everything))

    await transport.send(_subscriber(), _event())

    assert sender.posts == [
        ("https://receiver.test/hook", {"Webhook-Id": "evt_1"}, b'{"total":10}'),
    ]


async def test_a_200_answer_is_a_delivery() -> None:
    await _transport(FakeHttpSender(status_code=200)).send(_subscriber(), _event())


async def test_a_299_answer_is_still_a_delivery() -> None:
    await _transport(FakeHttpSender(status_code=299)).send(_subscriber(), _event())


@pytest.mark.parametrize("status_code", [199, 300, 302, 404, 500])
async def test_an_answer_outside_2xx_raises_a_delivery_error(status_code: int) -> None:
    transport = _transport(FakeHttpSender(status_code=status_code))

    with pytest.raises(DeliveryError) as caught:
        await transport.send(_subscriber(), _event())

    assert caught.value.status_code == status_code
    assert caught.value.url == "https://receiver.test/hook"


async def test_a_refused_delivery_says_what_came_back() -> None:
    transport = _transport(FakeHttpSender(status_code=500))

    with pytest.raises(
        DeliveryError,
        match=r'^The webhook to "https://receiver\.test/hook" was answered with HTTP 500\.$',
    ):
        await transport.send(_subscriber(), _event())


async def test_a_chain_that_never_wrote_a_body_is_refused_before_posting() -> None:
    sender = FakeHttpSender()
    transport = _transport(sender, body=FakeRequestConfigurator())

    with pytest.raises(LogicError, match=r"^The body must be set\.$"):
        await transport.send(_subscriber(), _event())

    assert sender.posts == []
