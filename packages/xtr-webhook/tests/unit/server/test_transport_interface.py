from __future__ import annotations

from tests.support.fake_http_sender import FakeHttpSender
from tests.support.fake_request_configurator import FakeRequestConfigurator
from xtr_webhook.server import Transport, TransportInterface


def test_the_transport_this_package_ships_satisfies_it() -> None:
    transport = Transport(
        sender=FakeHttpSender(),
        headers=FakeRequestConfigurator(),
        body=FakeRequestConfigurator(),
        signer=FakeRequestConfigurator(),
    )

    assert isinstance(transport, TransportInterface)


def test_something_that_cannot_send_does_not() -> None:
    assert not isinstance(object(), TransportInterface)


def test_anything_that_sends_satisfies_it() -> None:
    class Elsewhere:
        async def send(self, subscriber: object, event: object) -> None:
            del subscriber, event

    assert isinstance(Elsewhere(), TransportInterface)
