from __future__ import annotations

import pytest
from xtr_messenger import default_registry
from xtr_remote_event import RemoteEvent

from tests.support.fake_transport import FakeTransport
from xtr_webhook.exception import DeliveryError
from xtr_webhook.messenger import SendWebhookHandler, SendWebhookMessage
from xtr_webhook.subscriber import Subscriber


def _subscriber(url: str = "https://receiver.test/hook") -> Subscriber:
    return Subscriber(url, "s3cr3t")


def _event(event_id: str = "evt_1") -> RemoteEvent:
    return RemoteEvent(name="order.created", id=event_id, payload={"total": 10})


def test_it_is_declared_as_the_handler_of_the_message() -> None:
    declared = default_registry().handlers_for(SendWebhookMessage)

    assert [d.handler for d in declared] == [SendWebhookHandler]


@pytest.mark.anyio
async def test_it_hands_the_subscriber_and_the_event_to_the_transport() -> None:
    transport = FakeTransport()
    subscriber, event = _subscriber(), _event()

    await SendWebhookHandler(transport)(SendWebhookMessage(subscriber, event))

    assert transport.sends == [(subscriber, event)]


@pytest.mark.anyio
async def test_it_hands_over_the_objects_the_message_carried() -> None:
    transport = FakeTransport()
    subscriber, event = _subscriber(), _event()

    await SendWebhookHandler(transport)(SendWebhookMessage(subscriber, event))

    sent_subscriber, sent_event = transport.sends[0]
    assert sent_subscriber is subscriber
    assert sent_event is event


@pytest.mark.anyio
async def test_each_message_is_one_delivery() -> None:
    transport = SendWebhookHandler(fake := FakeTransport())

    await transport(SendWebhookMessage(_subscriber("https://first.test/hook"), _event("evt_1")))
    await transport(SendWebhookMessage(_subscriber("https://second.test/hook"), _event("evt_2")))

    assert [subscriber.url for subscriber, _ in fake.sends] == [
        "https://first.test/hook",
        "https://second.test/hook",
    ]


@pytest.mark.anyio
async def test_a_refused_delivery_comes_back_out_of_the_handler() -> None:
    refusal = DeliveryError(500, "https://receiver.test/hook")
    handler = SendWebhookHandler(FakeTransport(raises=refusal))

    with pytest.raises(DeliveryError) as caught:
        await handler(SendWebhookMessage(_subscriber(), _event()))

    assert caught.value is refusal


@pytest.mark.anyio
async def test_anything_else_the_transport_raises_comes_back_too() -> None:
    failure = TimeoutError("the receiver never answered")
    handler = SendWebhookHandler(FakeTransport(raises=failure))

    with pytest.raises(TimeoutError) as caught:
        await handler(SendWebhookMessage(_subscriber(), _event()))

    assert caught.value is failure
