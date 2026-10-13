from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_http_client_contracts import OPTIONS_DEFAULTS

from xtr_http_client import HttpClientMixin
from xtr_http_client.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence


def _normalized(options: Mapping[str, object]) -> Mapping[str, Sequence[str]]:
    return cast("Mapping[str, Sequence[str]]", options["normalized_headers"])


def test_a_client_starts_from_the_contract_defaults() -> None:
    client = HttpClientMixin()

    assert client._default_options["timeout"] == OPTIONS_DEFAULTS.get("timeout")
    assert client._default_options["max_redirects"] == 20


def test_the_defaults_a_client_was_built_with_win_over_the_contract_ones() -> None:
    client = HttpClientMixin({"timeout": 2.0, "headers": {"X-Trace": "abc"}})

    assert client._default_options["timeout"] == 2.0
    assert _normalized(client._default_options)["x-trace"] == ["X-Trace: abc"]


def test_a_client_with_other_options_is_a_copy_of_the_one_it_came_from() -> None:
    client = HttpClientMixin({"timeout": 2.0})

    other = client.with_options(timeout=3.0, headers={"X-Trace": "abc"})

    assert other is not client
    assert other._default_options["timeout"] == 3.0
    assert client._default_options["timeout"] == 2.0
    assert _normalized(other._default_options)["x-trace"] == ["X-Trace: abc"]
    assert "x-trace" not in _normalized(client._default_options)


def test_a_client_with_an_option_no_client_knows_is_refused() -> None:
    client = HttpClientMixin()
    # An untyped caller is exactly what the refusal is here for; the typed one
    # is refused by `RequestOptions` before anything runs.
    untyped = cast("Callable[..., object]", client.with_options)

    with pytest.raises(InvalidArgumentError) as raised:
        _ = untyped(timout=1.0)

    assert 'Unsupported option "timout" passed to "HttpClientMixin"' in str(raised.value)


def test_the_request_a_client_makes_is_prepared_against_its_own_defaults() -> None:
    client = HttpClientMixin({"base_uri": "http://example.com", "headers": {"X-Trace": "abc"}})

    url, options = client.prepare_request("GET", "/orders", {}, client._default_options)

    assert str(url) == "http://example.com/orders"
    assert _normalized(options)["x-trace"] == ["X-Trace: abc"]


def test_the_helpers_the_whole_request_is_built_with_are_reachable_on_the_client() -> None:
    assert HttpClientMixin.remove_dot_segments("/a/b/..") == "/a/"
    assert str(HttpClientMixin.parse_url("http://example.com")) == "http://example.com"
    assert HttpClientMixin.merge_query_string("a=1", {"a": 2}, replace=True) == "a=2"
    assert HttpClientMixin.normalize_headers({"Accept": "*/*"}) == {"accept": ["Accept: */*"]}
    assert HttpClientMixin.normalize_body(b"foo=bar") == b"foo=bar"
    assert HttpClientMixin.json_encode({"a": 1}) == b'{"a":1}'
    assert HttpClientMixin.normalize_peer_fingerprint({"sha1": "ab:cd"}) == {"sha1": "abcd"}
    assert HttpClientMixin.should_buffer({"content-type": ["application/json"]}) is True
    assert HttpClientMixin.get_proxy(None, HttpClientMixin.parse_url("http://a/"), None) is None
    assert (
        str(
            HttpClientMixin.resolve_url(
                HttpClientMixin.parse_url("/orders"),
                HttpClientMixin.parse_url("http://example.com"),
            )
        )
        == "http://example.com/orders"
    )


def test_the_options_a_request_merges_over_are_the_ones_the_client_keeps() -> None:
    client = HttpClientMixin()

    merged = client.merge_default_options({"timeout": 5.0}, client._default_options)

    assert merged["timeout"] == 5.0
    assert merged["max_redirects"] == 20
