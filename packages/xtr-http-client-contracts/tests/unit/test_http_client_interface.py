from __future__ import annotations

from tests.support.fake_http_client import FakeHttpClient
from xtr_http_client_contracts import HttpClientInterface


def test_a_client_answering_every_call_satisfies_it() -> None:
    client: HttpClientInterface = FakeHttpClient()

    assert isinstance(client, HttpClientInterface)


def test_an_unrelated_object_does_not() -> None:
    assert not isinstance(object(), HttpClientInterface)
