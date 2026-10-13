from __future__ import annotations

import pytest

from tests.support.fake_http_client import FakeHttpClient
from xtr_http_client_contracts import RequestOptions

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
    "timeout",
    "max_duration",
    "max_connect_duration",
    "resolve",
    "proxy",
    "verify_peer",
    "verify_host",
    "cafile",
    "capath",
    "local_cert",
    "local_pk",
    "passphrase",
    "max_retries",
    "extra",
}


def test_the_options_are_exactly_the_ones_the_contract_names() -> None:
    assert set(RequestOptions.__annotations__) == OPTION_NAMES


def test_no_option_is_required() -> None:
    assert RequestOptions.__required_keys__ == frozenset()
    assert RequestOptions.__optional_keys__ == frozenset(OPTION_NAMES)


def test_a_query_takes_scalars_and_sequences_that_repeat_the_name() -> None:
    options: RequestOptions = {"query": {"page": 2, "tags": ["new", "sale"]}}

    assert options["query"] == {"page": 2, "tags": ["new", "sale"]}


async def test_a_prepared_mapping_of_options_goes_straight_into_a_request() -> None:
    client = FakeHttpClient()
    options: RequestOptions = {"timeout": 2.5, "max_redirects": 0}

    _ = await client.request("GET", "https://example.com/", **options)

    assert client.calls == [("GET", "https://example.com/", {"timeout": 2.5, "max_redirects": 0})]
