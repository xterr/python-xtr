from __future__ import annotations

import pytest
from xtr_http_client import MockHttpClient

from tests.support.dummy_transport_factory import DummyTransportFactory
from xtr_notifier.bundle._peers import EventDispatcherPeer, HttpClientPeer
from xtr_notifier.bundle._services import tagged_factory
from xtr_notifier.exception import LogicError


def test_a_tagged_factory_is_built_with_the_peers() -> None:
    client = MockHttpClient()

    factory = tagged_factory(DummyTransportFactory)(
        HttpClientPeer(client), EventDispatcherPeer(None)
    )

    assert isinstance(factory, DummyTransportFactory)
    assert factory._http_client is client


def test_a_tagged_factory_refuses_to_be_built_without_an_http_client() -> None:
    build = tagged_factory(DummyTransportFactory)

    with pytest.raises(LogicError) as caught:
        _ = build(HttpClientPeer(None), EventDispatcherPeer(None))

    assert str(caught.value) == (
        'The "DummyTransportFactory" transport factory needs an HTTP client; '
        "install xtr-http-client beside xtr-notifier."
    )
