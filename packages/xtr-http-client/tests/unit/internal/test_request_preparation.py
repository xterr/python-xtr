from __future__ import annotations

import ssl
from typing import TYPE_CHECKING, cast

import pytest
from xtr_http_client_contracts import OPTIONS_DEFAULTS

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.request_preparation import prepare_request

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_client_contracts import QueryValue

_CLIENT = "FakeClient"


def _defaults(options: Mapping[str, object] | None = None) -> dict[str, object]:
    _, prepared = prepare_request(_CLIENT, None, None, dict(options or {}))
    return prepared


def _headers(options: Mapping[str, object]) -> Sequence[str]:
    return cast("Sequence[str]", options["headers"])


def _normalized(options: Mapping[str, object]) -> Mapping[str, Sequence[str]]:
    return cast("Mapping[str, Sequence[str]]", options["normalized_headers"])


@pytest.mark.parametrize(
    ("expected", "url", "query"),
    [
        ("http://example.com/", "http://example.com/", {}),
        ("http://example.com/?a=1&b=b", ".", {}),
        ("http://example.com/?a=2&b=b", ".?a=2", {}),
        ("http://example.com/?a=3&b=b", ".", {"a": 3}),
        ("http://example.com/?a=3&b=b", ".?a=0", {"a": 3}),
        ("http://example.com/", "http://example.com/", {"a": None}),
        ("http://example.com/?b=", "http://example.com/", {"b": ""}),
        ("http://example.com/?b=", "http://example.com/", {"a": None, "b": ""}),
        ("http://example.com/?a=3&a=4&b=b", ".", {"a": [3, 4]}),
        ("http://example.com/?c=3&c=4&a=1&b=b", ".?c=0", {"c": [3, 4]}),
        ("http://example.com/?b=b", "http://example.com/?a=0&a=1&b=b", {"a": None}),
    ],
)
def test_a_url_is_resolved_against_the_base_uri_and_the_default_query(
    expected: str,
    url: str,
    query: Mapping[str, QueryValue],
) -> None:
    defaults = _defaults({"base_uri": "http://example.com?c=c", "query": {"a": 1, "b": "b"}})

    prepared_url, _ = prepare_request(_CLIENT, None, url, {"query": query}, defaults)

    assert str(prepared_url) == expected


def test_no_url_leaves_the_base_uri_and_the_credentials_for_the_next_request() -> None:
    _, defaults = prepare_request(
        _CLIENT,
        None,
        None,
        {"base_uri": "http://example.com", "auth_bearer": "foobar"},
    )

    assert defaults["base_uri"] == "http://example.com"
    assert defaults["auth_bearer"] == "foobar"


def test_a_content_type_the_caller_chose_for_a_form_survives_the_defaults() -> None:
    defaults = _defaults(
        {"base_uri": "http://example.com?c=c", "query": {"a": 1, "b": "b"}, "body": {}},
    )

    _, options = prepare_request(
        _CLIENT,
        None,
        "http://example.com",
        {
            "body": {"1": "2"},
            "headers": {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
        },
        defaults,
    )

    assert "Content-Type: application/x-www-form-urlencoded; charset=utf-8" in _headers(options)


@pytest.mark.parametrize("method", ["get", "Get", "GET1", "GE T"])
def test_a_method_that_is_not_uppercase_letters_is_refused(method: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(_CLIENT, method, "http://example.com", {})

    assert str(raised.value) == (
        f'Invalid HTTP method "{method}", only uppercase letters are accepted.'
    )


def test_a_method_with_nothing_in_it_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(_CLIENT, "", "http://example.com", {})

    assert str(raised.value) == "The HTTP method cannot be empty."


def test_a_bearer_token_is_sent_as_an_authorization_header() -> None:
    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"auth_bearer": "foobar"},
        dict(OPTIONS_DEFAULTS),
    )

    assert _headers(options) == [
        "Accept: */*",
        "Content-Type: application/x-www-form-urlencoded",
        "Authorization: Bearer foobar",
    ]
    assert _normalized(options)["authorization"] == ["Authorization: Bearer foobar"]


def test_the_credentials_are_gone_from_the_options_once_they_are_a_header() -> None:
    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"auth_bearer": "foobar"},
        dict(OPTIONS_DEFAULTS),
    )

    assert "auth_bearer" not in options
    assert "auth_basic" not in options
    assert "base_uri" not in options


def test_an_authorization_the_caller_wrote_is_not_overwritten() -> None:
    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"auth_bearer": "foobar", "headers": {"Authorization": "Bearer other"}},
        dict(OPTIONS_DEFAULTS),
    )

    assert _normalized(options)["authorization"] == ["Authorization: Bearer other"]


def test_a_bearer_token_that_is_not_text_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(
            _CLIENT,
            "POST",
            "http://example.com",
            {"auth_bearer": 5},
            dict(OPTIONS_DEFAULTS),
        )

    assert str(raised.value) == 'Option "auth_bearer" must be a string, "int" given.'


def test_a_bearer_token_that_would_split_the_head_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(
            _CLIENT,
            "POST",
            "http://example.com",
            {"auth_bearer": "a\nb"},
            dict(OPTIONS_DEFAULTS),
        )

    assert str(raised.value) == 'Invalid character found in option "auth_bearer": "a\\nb".'


def test_asking_for_both_kinds_of_credentials_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(
            _CLIENT,
            "POST",
            "http://example.com",
            {"auth_bearer": "foo", "auth_basic": "foo:bar"},
            dict(OPTIONS_DEFAULTS),
        )

    assert str(raised.value) == (
        'Define either the "auth_basic" or the "auth_bearer" option, setting both is not supported.'
    )


@pytest.mark.parametrize(
    ("auth_basic", "expected"),
    [
        ("foo:bar", "Zm9vOmJhcg=="),
        (("foo", "bar"), "Zm9vOmJhcg=="),
        ("foo", "Zm9v"),
        (("foo",), "Zm9v"),
    ],
)
def test_basic_credentials_are_sent_as_a_base64_authorization(
    auth_basic: str | tuple[str, ...],
    expected: str,
) -> None:
    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"auth_basic": auth_basic},
        dict(OPTIONS_DEFAULTS),
    )

    assert _normalized(options)["authorization"][0] == f"Authorization: Basic {expected}"


@pytest.mark.parametrize("auth_basic", [(), ("a", "b", "c")])
def test_basic_credentials_of_any_other_length_are_refused(auth_basic: tuple[str, ...]) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(
            _CLIENT,
            "POST",
            "http://example.com",
            {"auth_basic": auth_basic},
            dict(OPTIONS_DEFAULTS),
        )

    assert str(raised.value) == (
        f'Option "auth_basic" must contain 1 or 2 elements, "{len(auth_basic)}" given.'
    )


def test_basic_credentials_of_another_shape_are_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(
            _CLIENT,
            "POST",
            "http://example.com",
            {"auth_basic": 5},
            dict(OPTIONS_DEFAULTS),
        )

    assert str(raised.value) == 'Option "auth_basic" must be a string or a tuple, "int" given.'


def test_asking_for_both_a_json_and_a_body_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(
            _CLIENT,
            "POST",
            "http://example.com",
            {"json": {"foo": "bar"}, "body": "<html/>"},
            dict(OPTIONS_DEFAULTS),
        )

    assert str(raised.value) == (
        'Define either the "json" or the "body" option, setting both is not supported.'
    )


def test_a_json_option_becomes_the_body_and_names_its_content_type() -> None:
    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"json": {"foo": "bar"}},
        dict(OPTIONS_DEFAULTS),
    )

    assert options["body"] == b'{"foo":"bar"}'
    assert "json" not in options
    assert _normalized(options)["content-type"] == ["Content-Type: application/json"]
    assert _normalized(options)["content-length"] == ["Content-Length: 13"]


def test_a_json_option_keeps_a_content_type_the_caller_chose() -> None:
    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"json": {"foo": "bar"}, "headers": {"Content-Type": "application/ld+json"}},
        dict(OPTIONS_DEFAULTS),
    )

    assert _normalized(options)["content-type"] == ["Content-Type: application/ld+json"]


def test_an_empty_body_next_to_a_json_option_is_not_a_body() -> None:
    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"json": {"foo": "bar"}, "body": ""},
        dict(OPTIONS_DEFAULTS),
    )

    assert options["body"] == b'{"foo":"bar"}'


def test_every_request_says_what_it_accepts() -> None:
    _, options = prepare_request(
        _CLIENT,
        "GET",
        "http://example.com",
        {},
        dict(OPTIONS_DEFAULTS),
    )

    assert _normalized(options)["accept"] == ["Accept: */*"]


def test_an_accept_header_the_caller_wrote_is_left_alone() -> None:
    _, options = prepare_request(
        _CLIENT,
        "GET",
        "http://example.com",
        {"headers": {"Accept": "text/plain"}},
        dict(OPTIONS_DEFAULTS),
    )

    assert _normalized(options)["accept"] == ["Accept: text/plain"]


def test_the_length_of_the_body_is_corrected_to_what_is_being_sent() -> None:
    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"body": "foo=bar", "headers": {"Content-Length": "99"}},
        dict(OPTIONS_DEFAULTS),
    )

    assert _normalized(options)["content-length"] == ["Content-Length: 7"]


def test_a_length_that_is_already_right_is_left_alone() -> None:
    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"body": "foo=0123456789", "headers": {"Content-Length": "14"}},
        dict(OPTIONS_DEFAULTS),
    )

    assert _normalized(options)["content-length"] == ["Content-Length: 14"]


def test_an_empty_body_nobody_declared_a_length_for_gets_no_length() -> None:
    _, options = prepare_request(
        _CLIENT,
        "GET",
        "http://example.com",
        {},
        dict(OPTIONS_DEFAULTS),
    )

    assert "content-length" not in _normalized(options)


@pytest.mark.parametrize(
    ("method", "body", "expected"),
    [
        ("POST", b"", True),
        ("GET", "foo=bar", True),
        ("GET", b"", False),
    ],
)
def test_a_body_with_no_content_type_is_sent_as_a_form(
    method: str,
    body: bytes | str,
    expected: bool,
) -> None:
    _, options = prepare_request(
        _CLIENT,
        method,
        "http://example.com",
        {"body": body},
        dict(OPTIONS_DEFAULTS),
    )

    form = "Content-Type: application/x-www-form-urlencoded"
    assert (form in _headers(options)) is expected


def test_the_content_type_a_json_body_named_is_not_replaced_by_the_form_one() -> None:
    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"json": {"foo": "bar"}},
        dict(OPTIONS_DEFAULTS),
    )

    assert "Content-Type: application/x-www-form-urlencoded" not in _headers(options)


def test_the_options_a_request_is_made_with_are_resolved_to_numbers() -> None:
    _, options = prepare_request(
        _CLIENT,
        "GET",
        "http://example.com",
        {},
        dict(OPTIONS_DEFAULTS),
    )

    assert options["timeout"] == 60.0
    assert options["max_duration"] == 0.0
    assert options["max_connect_duration"] == 0.0
    assert options["http_version"] is None


def test_a_timeout_below_zero_is_as_good_as_none() -> None:
    _, options = prepare_request(
        _CLIENT,
        "GET",
        "http://example.com",
        {"timeout": -1.0},
        dict(OPTIONS_DEFAULTS),
    )

    assert options["timeout"] == 172800.0


def test_a_http_version_is_kept_as_the_text_it_was_asked_for_by() -> None:
    _, options = prepare_request(
        _CLIENT,
        "GET",
        "http://example.com",
        {"http_version": "2.0"},
        dict(OPTIONS_DEFAULTS),
    )

    assert options["http_version"] == "2.0"


def test_a_fingerprint_is_normalized_on_the_way_through() -> None:
    _, options = prepare_request(
        _CLIENT,
        "GET",
        "https://example.com",
        {"peer_fingerprint": "d41d8cd98f00b204e9800998ecf8427e"},
        dict(OPTIONS_DEFAULTS),
    )

    assert options["peer_fingerprint"] == {"md5": "d41d8cd98f00b204e9800998ecf8427e"}


def test_a_buffer_that_is_neither_a_choice_nor_a_decision_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(
            _CLIENT,
            "GET",
            "http://example.com",
            {"buffer": 5},
            dict(OPTIONS_DEFAULTS),
        )

    assert str(raised.value) == 'Option "buffer" must be a bool or a callable, "int" given.'


def test_a_progress_callback_that_cannot_be_called_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(
            _CLIENT,
            "GET",
            "http://example.com",
            {"on_progress": 5},
            dict(OPTIONS_DEFAULTS),
        )

    assert str(raised.value) == 'Option "on_progress" must be callable, "int" given.'


def test_a_tls_floor_that_is_not_a_version_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(
            _CLIENT,
            "GET",
            "https://example.com",
            {"crypto_method": "TLSv1.2"},
            dict(OPTIONS_DEFAULTS),
        )

    assert str(raised.value) == (
        'Option "crypto_method" must be one of the TLS versions, "str" given.'
    )


def test_the_tls_floor_of_the_defaults_is_let_through() -> None:
    _, options = prepare_request(
        _CLIENT,
        "GET",
        "https://example.com",
        {"crypto_method": ssl.TLSVersion.TLSv1_3},
        dict(OPTIONS_DEFAULTS),
    )

    assert options["crypto_method"] == ssl.TLSVersion.TLSv1_3


def test_a_body_produced_in_pieces_is_sent_without_a_length() -> None:
    chunks = [b"foo=bar"]

    _, options = prepare_request(
        _CLIENT,
        "POST",
        "http://example.com",
        {"body": chunks},
        dict(OPTIONS_DEFAULTS),
    )

    assert options["body"] is chunks
    assert "content-length" not in _normalized(options)
    assert "Content-Type: application/x-www-form-urlencoded" in _headers(options)


def test_a_timeout_that_is_not_a_number_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = prepare_request(
            _CLIENT,
            "GET",
            "http://example.com",
            {"timeout": "soon"},
            dict(OPTIONS_DEFAULTS),
        )

    assert str(raised.value) == 'Option "timeout" must be a number, "str" given.'
