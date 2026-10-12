from __future__ import annotations

import pytest
from xtr_remote_event import RemoteEvent

from tests.support.fake_transport import FakeTransport
from xtr_webhook.exception import DeliveryError
from xtr_webhook.server import TransportInterface
from xtr_webhook.subscriber import Subscriber

pytestmark = pytest.mark.anyio


def _subscriber(url: str = "https://receiver.test/hook") -> Subscriber:
    return Subscriber(url, "s3cr3t")


def _event(event_id: str = "evt_1") -> RemoteEvent:
    return RemoteEvent(name="order.created", id=event_id, payload={"total": 10})


def test_it_is_a_transport() -> None:
    assert isinstance(FakeTransport(), TransportInterface)


async def test_it_records_nothing_before_it_is_used() -> None:
    assert FakeTransport().sends == []


async def test_it_records_every_send_in_order() -> None:
    transport = FakeTransport()
    first, second = _subscriber("https://first.test/hook"), _subscriber("https://second.test/hook")

    await transport.send(first, _event("evt_1"))
    await transport.send(second, _event("evt_2"))

    assert transport.sends == [(first, _event("evt_1")), (second, _event("evt_2"))]


async def test_it_records_the_subscriber_and_the_event_it_was_handed() -> None:
    transport = FakeTransport()
    subscriber, event = _subscriber(), _event()

    await transport.send(subscriber, event)

    recorded_subscriber, recorded_event = transport.sends[0]
    assert recorded_subscriber is subscriber
    assert recorded_event is event


async def test_it_raises_what_it_was_built_with() -> None:
    transport = FakeTransport(raises=DeliveryError(500, "https://receiver.test/hook"))

    with pytest.raises(DeliveryError) as caught:
        await transport.send(_subscriber(), _event())

    assert caught.value.status_code == 500


async def test_a_send_it_refuses_is_still_recorded() -> None:
    transport = FakeTransport(raises=DeliveryError(500, "https://receiver.test/hook"))

    with pytest.raises(DeliveryError):
        await transport.send(_subscriber(), _event())

    assert transport.sends == [(_subscriber(), _event())]
