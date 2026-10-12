from __future__ import annotations

import httpx
import pytest
from xtr_remote_event import RemoteEvent

from tests.support.fake_request_configurator import FakeRequestConfigurator
from xtr_webhook.bridge.httpx import HttpxSender
from xtr_webhook.exception import DeliveryError
from xtr_webhook.server import HttpSenderInterface, OutgoingRequest, Transport
from xtr_webhook.subscriber import Subscriber

pytestmark = pytest.mark.anyio


def _recording(seen: list[httpx.Request], status_code: int = 202) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status_code)

    return httpx.MockTransport(handler)


async def test_it_is_an_http_sender() -> None:
    async with httpx.AsyncClient(transport=_recording([])) as client:
        assert isinstance(HttpxSender(client), HttpSenderInterface)


async def test_it_posts_and_returns_the_status() -> None:
    async with httpx.AsyncClient(transport=_recording([], status_code=500)) as client:
        sender = HttpxSender(client)

        assert await sender.post("https://receiver.test/hook", {}, b"{}") == 500


async def test_the_url_the_headers_and_the_body_reach_the_wire_exactly() -> None:
    seen: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=_recording(seen)) as client:
        sender = HttpxSender(client)

        _ = await sender.post(
            "https://receiver.test/hook",
            {"Webhook-Id": "evt_1", "Webhook-Signature": "sha256=abc"},
            b'{"total":10}',
        )

    assert seen[0].method == "POST"
    assert str(seen[0].url) == "https://receiver.test/hook"
    assert seen[0].headers["Webhook-Id"] == "evt_1"
    assert seen[0].headers["Webhook-Signature"] == "sha256=abc"
    assert seen[0].content == b'{"total":10}'


async def test_a_redirect_is_returned_rather_than_followed() -> None:
    """Even on a client built to follow redirects: the post says not to, so a
    3xx comes back as the answer — one request on the wire, nothing re-sent to
    wherever the receiver pointed."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://elsewhere.test/hook"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as client:
        sender = HttpxSender(client)

        assert await sender.post("https://receiver.test/hook", {}, b"{}") == 302

    assert len(seen) == 1


def _event() -> RemoteEvent:
    return RemoteEvent(name="order.created", id="evt_1", payload={"total": 10})


def _writes_headers(request: OutgoingRequest) -> None:
    request.headers["Webhook-Id"] = "evt_1"


def _writes_body(request: OutgoingRequest) -> None:
    request.body = b'{"total":10}'


def _writes_signature(request: OutgoingRequest) -> None:
    request.headers["Webhook-Signature"] = "sha256=abc"


def _transport(client: httpx.AsyncClient) -> Transport:
    return Transport(
        sender=HttpxSender(client),
        headers=FakeRequestConfigurator(write=_writes_headers),
        body=FakeRequestConfigurator(write=_writes_body),
        signer=FakeRequestConfigurator(write=_writes_signature),
    )


async def test_a_2xx_answer_delivers_through_the_sending_stack() -> None:
    seen: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=_recording(seen)) as client:
        await _transport(client).send(
            Subscriber("https://receiver.test/hook", "s3cr3t"),
            _event(),
        )

    assert str(seen[0].url) == "https://receiver.test/hook"
    assert seen[0].headers["Webhook-Id"] == "evt_1"
    assert seen[0].headers["Webhook-Signature"] == "sha256=abc"
    assert seen[0].content == b'{"total":10}'


@pytest.mark.parametrize("status_code", [302, 500])
async def test_an_answer_outside_2xx_raises_through_the_sending_stack(status_code: int) -> None:
    async with httpx.AsyncClient(transport=_recording([], status_code=status_code)) as client:
        with pytest.raises(DeliveryError) as caught:
            await _transport(client).send(
                Subscriber("https://receiver.test/hook", "s3cr3t"),
                _event(),
            )

    assert caught.value.status_code == status_code
    assert caught.value.url == "https://receiver.test/hook"
