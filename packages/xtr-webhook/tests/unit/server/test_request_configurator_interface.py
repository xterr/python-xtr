from __future__ import annotations

from tests.support.fake_payload_serializer import FakePayloadSerializer
from xtr_webhook.server import (
    HeadersConfigurator,
    HeaderSignatureConfigurator,
    JsonBodyConfigurator,
    RequestConfiguratorInterface,
)


def test_every_configurator_this_package_ships_satisfies_it() -> None:
    configurators = (
        HeadersConfigurator(),
        JsonBodyConfigurator(FakePayloadSerializer()),
        HeaderSignatureConfigurator(),
    )

    assert [one for one in configurators if not isinstance(one, RequestConfiguratorInterface)] == []


def test_something_that_cannot_configure_a_request_does_not() -> None:
    assert not isinstance(object(), RequestConfiguratorInterface)


def test_anything_that_configures_a_request_satisfies_it() -> None:
    class Elsewhere:
        def configure(self, event: object, secret: str, request: object) -> None:
            del event, secret, request

    assert isinstance(Elsewhere(), RequestConfiguratorInterface)
