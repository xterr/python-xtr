from __future__ import annotations

import pytest

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.option_merge import merge_default_options

_CLIENT = "FakeClient"


def _defaults(**overrides: object) -> dict[str, object]:
    """Defaults that know about every option a merge always sets."""
    return {"headers": {}, "query": {}, **overrides}


def test_a_header_the_request_did_not_name_is_taken_from_the_defaults() -> None:
    merged = merge_default_options(
        _CLIENT,
        {"headers": {"Accept": "text/plain"}},
        _defaults(headers={"Accept": "*/*", "X-Trace": "abc"}),
    )

    assert merged["normalized_headers"] == {
        "accept": ["Accept: text/plain"],
        "x-trace": ["X-Trace: abc"],
    }
    assert merged["headers"] == ["Accept: text/plain", "X-Trace: abc"]


def test_an_option_the_request_did_not_name_is_taken_from_the_defaults() -> None:
    merged = merge_default_options(
        _CLIENT,
        {"timeout": 1.0},
        _defaults(timeout=2.0, max_duration=3.0),
    )

    assert merged["timeout"] == 1.0
    assert merged["max_duration"] == 3.0


def test_a_query_is_never_inherited_from_the_defaults() -> None:
    merged = merge_default_options(_CLIENT, {}, _defaults(query={"a": 1}))

    assert merged["query"] == {}


def test_the_extra_entries_of_the_defaults_fill_in_the_ones_not_given() -> None:
    merged = merge_default_options(
        _CLIENT,
        {"extra": {"a": 1}},
        _defaults(extra={"a": 2, "b": 3}),
    )

    assert merged["extra"] == {"a": 1, "b": 3}


@pytest.mark.parametrize(
    ("host", "address", "expected_host", "expected_address"),
    [
        ("Example.COM", "127.0.0.1", "example.com", "127.0.0.1"),
        ("example.com:8080", "127.0.0.1", "example.com:8080", "127.0.0.1"),
        ("example.com", "[::1]", "example.com", "::1"),
        ("example.com", "", "example.com", None),
    ],
)
def test_a_pinned_address_is_keyed_by_the_host_as_a_url_would_name_it(
    host: str,
    address: str,
    expected_host: str,
    expected_address: str | None,
) -> None:
    merged = merge_default_options(_CLIENT, {"resolve": {host: address}}, _defaults(resolve={}))

    assert merged["resolve"] == {expected_host: expected_address}


def test_an_address_pinned_by_the_defaults_fills_in_a_host_the_request_did_not_pin() -> None:
    merged = merge_default_options(
        _CLIENT,
        {"resolve": {"a.example.com": "127.0.0.1"}},
        _defaults(resolve={"a.example.com": "127.0.0.2", "B.example.com": "127.0.0.3"}),
    )

    assert merged["resolve"] == {
        "a.example.com": "127.0.0.1",
        "b.example.com": "127.0.0.3",
    }


def test_an_option_no_client_knows_is_refused_with_the_closest_ones_named() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = merge_default_options(_CLIENT, {"timout": 1.0}, {"timeout": 2.0, "query": {}})

    assert str(raised.value) == (
        'Unsupported option "timout" passed to "FakeClient", did you mean "timeout"?'
    )


def test_an_option_nothing_resembles_is_refused_with_every_option_named() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = merge_default_options(_CLIENT, {"nonsense": 1}, {"timeout": 2.0, "query": {}})

    assert str(raised.value) == (
        'Unsupported option "nonsense" passed to "FakeClient", did you mean "timeout", "query"?'
    )


def test_an_option_a_longer_one_contains_is_named_as_an_alternative() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = merge_default_options(_CLIENT, {"cert": "a.pem"}, {"local_cert": None, "query": {}})

    assert str(raised.value) == (
        'Unsupported option "cert" passed to "FakeClient", did you mean "local_cert"?'
    )


def test_an_unknown_option_is_let_through_when_extra_options_are_allowed() -> None:
    merged = merge_default_options(
        _CLIENT,
        {"nonsense": 1},
        {"timeout": 2.0},
        allow_extra_options=True,
    )

    assert merged["nonsense"] == 1


def test_nothing_is_refused_when_there_are_no_defaults_to_compare_with() -> None:
    merged = merge_default_options(_CLIENT, {"nonsense": 1}, {})

    assert merged["nonsense"] == 1
