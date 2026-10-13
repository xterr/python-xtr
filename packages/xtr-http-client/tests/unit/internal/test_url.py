from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.url import parse_url, remove_dot_segments, resolve_url

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import QueryValue

_BASE = "http://a/b/c/d;p?q"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("g", "http://a/b/c/g"),
        ("./g", "http://a/b/c/g"),
        ("g/", "http://a/b/c/g/"),
        ("/g", "http://a/g"),
        ("//g", "http://g/"),
        ("?y", "http://a/b/c/d;p?y"),
        ('?y={"f":1}', "http://a/b/c/d;p?y={%22f%22:1}"),
        ("g{oof}y", "http://a/b/c/g{oof}y"),
        ("g?y", "http://a/b/c/g?y"),
        ("#s", "http://a/b/c/d;p?q#s"),
        ("g#s", "http://a/b/c/g#s"),
        ("g?y#s", "http://a/b/c/g?y#s"),
        (";x", "http://a/b/c/;x"),
        ("g;x", "http://a/b/c/g;x"),
        ("g;x?y#s", "http://a/b/c/g;x?y#s"),
        ("", _BASE),
        (".", "http://a/b/c/"),
        ("./", "http://a/b/c/"),
        ("..", "http://a/b/"),
        ("../", "http://a/b/"),
        ("../g", "http://a/b/g"),
        ("../..", "http://a/"),
        ("../../", "http://a/"),
        ("../../g", "http://a/g"),
        ("../../../g", "http://a/g"),
        ("../../../../g", "http://a/g"),
        ("/./g", "http://a/g"),
        ("/../g", "http://a/g"),
        ("g.", "http://a/b/c/g."),
        (".g", "http://a/b/c/.g"),
        ("g..", "http://a/b/c/g.."),
        ("..g", "http://a/b/c/..g"),
        ("./../g", "http://a/b/g"),
        ("foo////g", "http://a/b/c/foo////g"),
        ("./g/.", "http://a/b/c/g/"),
        ("g/./h", "http://a/b/c/g/h"),
        ("g/../h", "http://a/b/c/h"),
        ("g;x=1/./y", "http://a/b/c/g;x=1/y"),
        ("g;x=1/../y", "http://a/b/c/y"),
        ("g/h:123/i", "http://a/b/c/g/h:123/i"),
        ("g?y/./x", "http://a/b/c/g?y/./x"),
        ("g?y/../x", "http://a/b/c/g?y/../x"),
        ("g#s/./x", "http://a/b/c/g#s/./x"),
        ("g#s/../x", "http://a/b/c/g#s/../x"),
        ("?y#s", "http://a/b/c/d;p?y#s"),
        ("//0", "http://0/"),
        ("0", "http://a/b/c/0"),
        ("?0", "http://a/b/c/d;p?0"),
        ("#0", "http://a/b/c/d;p?q#0"),
    ],
)
def test_a_relative_url_resolves_against_the_base(url: str, expected: str) -> None:
    assert str(resolve_url(parse_url(url), parse_url(_BASE))) == expected


@pytest.mark.parametrize(
    ("base", "url", "expected"),
    [
        ("http://a/b/c?q#s", "?y", "http://a/b/c?y"),
        ("http://u@a/b/c/d;p?q", ".", "http://u@a/b/c/"),
        ("http://u:p@a/b/c/d;p?q", ".", "http://u:p@a/b/c/"),
        ("http://a/b/c/d/", "e", "http://a/b/c/d/e"),
    ],
)
def test_the_base_carries_its_user_info_and_its_trailing_slash(
    base: str,
    url: str,
    expected: str,
) -> None:
    assert str(resolve_url(parse_url(url), parse_url(base))) == expected


def test_a_url_with_no_scheme_and_no_base_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = resolve_url(parse_url("/foo"), None)

    assert str(raised.value) == (
        'Invalid URL: scheme is missing in "/foo". Did you forget to add "http(s)://"?'
    )


def test_a_base_without_a_host_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = resolve_url(parse_url("/foo"), parse_url("/bar"))

    assert str(raised.value) == 'Invalid "base_uri" option: host or scheme is missing in "/bar".'


def test_a_scheme_without_a_host_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = resolve_url(parse_url("http:bar"), None)

    assert str(raised.value) == 'Invalid URL: host is missing in "http:bar".'


@pytest.mark.parametrize("url", ["localhost:8080", "localhost:8081"])
def test_a_host_and_port_without_a_scheme_reads_as_an_unsupported_scheme(url: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = parse_url(url)

    assert str(raised.value) == f'Unsupported scheme in "{url}": "http" or "https" expected.'


@pytest.mark.parametrize(
    "url",
    [
        "http://foo.com\\bar",
        "\\\\foo.com/bar",
        "a\nb",
        "a\rb",
        "a\tb",
        " foo",
        "foo ",
        "\x0bfoo",
        "foo\x0b",
        "//",
        "http://a:bc/",
    ],
)
def test_a_malformed_url_is_refused(url: str) -> None:
    with pytest.raises(InvalidArgumentError, match="Malformed URL"):
        _ = parse_url(url)


@pytest.mark.parametrize(
    ("expected", "url", "query"),
    [
        (("http:", "//example.com", None, None, None), "http://Example.coM:80", {}),
        (
            ("https:", "//xn--dj-kia8a.example.com:8000", "/", None, None),
            "https://DÉjà.Example.com:8000/",
            {},
        ),
        ((None, None, "/f%20o.o", "?a=b", "#c"), "/f o%2Eo?a=b#c", {}),
        (
            (
                None,
                None,
                "/custom%7C2010-01-01%2000:00:00%7C2023-06-15%2005:50:35",
                "?a=b",
                "#c",
            ),
            "/custom|2010-01-01 00:00:00|2023-06-15 05:50:35?a=b#c",
            {},
        ),
        ((None, "//a:b@foo", "/bar", None, None), "//a:b@foo/bar", {}),
        ((None, "//a:b@foo", "/b{}", None, None), "//a:b@foo/b{}", {}),
        (("http:", None, None, None, None), "http:", {}),
        (("http:", None, "bar", None, None), "http:bar", {}),
        (
            (None, None, "bar", "?a=1&c=c", None),
            "bar?a=a&b=b",
            {"b": None, "c": "c", "a": 1},
        ),
        (
            (
                None,
                None,
                "bar",
                "?a=b+c&b=b-._~!$%26/%27()[]*%2B%2C;%3D:@%25%5C%5E%60%7B%7C%7D",
                None,
            ),
            "bar?a=b+c",
            {"b": "b-._~!$&/'()[]*+,;=:@%\\^`{|}"},
        ),
        ((None, None, "bar", "?a=b%2B%20c", None), "bar?a=b+c", {"a": "b+ c"}),
        ((None, None, "bar", "?a[b]=c", None), "bar", {"a": {"b": "c"}}),
        ((None, None, "bar", "?a[b[c]=d", None), "bar?a[b[c]=d", {}),
        (
            (None, None, "bar", "?a[b][c]=dd", None),
            "bar?a[b][c]=d&e[f]=g",
            {"a": {"b": {"c": "dd"}}, "e[f]": None},
        ),
        (
            (None, None, "bar", "?a=b&a[b%20c]=d&e%3Df=%E2%9C%93", None),
            "bar?a=b",
            {"a": {"b c": "d"}, "e=f": "✓"},
        ),
        ((None, None, "bar", "?a[b]=2", None), "bar", {"a[b]": 1, "a": {"b": 2}}),
        (
            (None, None, "bar", "?a=b&a=c&d=1&e[]=f&e[]=g", None),
            "bar",
            {"a": ["b", "c"], "d": True, "e[]": ["f", "g"]},
        ),
        (
            (None, None, "bar", "?a=c&a=d&b=b&e=f", None),
            "bar?a=a&a=b&b=b&c=c",
            {"a": ["c", "d"], "c": None, "e": "f"},
        ),
        ((None, None, "bar", "?a=1&a=3&b=2", None), "bar", {"a": [1, 3], "b": 2}),
        ((None, None, "bar", "?1=a&1=b", None), "bar?1=c", {"1": ["a", "b"]}),
        (
            (None, None, "bar", "?a=b%20c&a=%E2%9C%93&d%3De=f%26g", None),
            "bar",
            {"a": ["b c", "✓"], "d=e": "f&g"},
        ),
    ],
)
def test_a_url_is_split_into_the_parts_a_request_is_built_from(
    expected: tuple[str | None, ...],
    url: str,
    query: Mapping[str, QueryValue],
) -> None:
    assert tuple(parse_url(url, query)) == expected


def test_a_query_parameter_that_is_neither_a_scalar_nor_a_collection_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = parse_url("http://example.com", cast("Mapping[str, QueryValue]", {"a": object()}))

    assert str(raised.value) == (
        'Invalid value for option "query": "object" is not a scalar, a sequence or a mapping.'
    )


@pytest.mark.parametrize(
    ("expected", "path"),
    [
        ("", ""),
        ("", "."),
        ("", ".."),
        ("a", "./a"),
        ("a", "../a"),
        ("/a/b", "/a/./b"),
        ("/b/", "/a/../b/."),
        ("/a//b/", "/a///../b/."),
        ("/a/", "/a/b/.."),
        ("/a///b", "/a///b"),
    ],
)
def test_dot_segments_are_taken_out_of_a_path(expected: str, path: str) -> None:
    assert remove_dot_segments(path) == expected


def test_an_ipv6_host_keeps_the_brackets_a_url_writes_it_in() -> None:
    assert str(parse_url("http://[::1]:8080/orders")) == "http://[::1]:8080/orders"
    assert str(parse_url("https://[2001:db8::1]/")) == "https://[2001:db8::1]/"


def test_a_host_no_resolver_could_be_asked_for_is_left_as_it_was_written() -> None:
    too_long = "é" * 70

    assert parse_url(f"http://{too_long}.test/").authority == f"//{too_long}.test"
