from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_http_client import FakeHttpClient
from xtr_http_client_contracts import RequestOptions

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import QueryValue

pytestmark = pytest.mark.anyio

OPTION_NAMES = {
    "auth_basic",
    "auth_bearer",
    "query",
    "headers",
    "body",
    "json",
    "user_data",
    "max_redirects",
    "http_version",
    "base_uri",
    "buffer",
    "on_progress",
    "resolve",
    "proxy",
    "no_proxy",
    "timeout",
    "max_duration",
    "max_connect_duration",
    "bindto",
    "verify_peer",
    "verify_host",
    "cafile",
    "capath",
    "local_cert",
    "local_pk",
    "passphrase",
    "ciphers",
    "peer_fingerprint",
    "capture_peer_cert_chain",
    "crypto_method",
    "extra",
}

NESTED_QUERY: Mapping[str, QueryValue] = {
    "page": 2,
    "tags": ["new", "sale"],
    "filter": {"since": None, "scores": [1.5, True]},
}


def test_the_options_are_exactly_the_ones_the_contract_names() -> None:
    assert set(RequestOptions.__annotations__) == OPTION_NAMES


def test_no_option_is_required() -> None:
    assert RequestOptions.__required_keys__ == frozenset()
    assert RequestOptions.__optional_keys__ == frozenset(OPTION_NAMES)


def test_a_query_value_may_nest_sequences_and_mappings() -> None:
    assert NESTED_QUERY["page"] == 2
    assert NESTED_QUERY["filter"] == {"since": None, "scores": [1.5, True]}


async def test_a_prepared_mapping_of_options_goes_straight_into_a_request() -> None:
    client = FakeHttpClient()
    options: RequestOptions = {"timeout": 2.5, "max_redirects": 0}

    _ = await client.request("GET", "https://example.com/", **options)

    assert client.calls == [("GET", "https://example.com/", {"timeout": 2.5, "max_redirects": 0})]
