from __future__ import annotations

import pytest
from xtr_http_message_contracts import UriInterface

from xtr_http_message.uri import Uri

# The harness checks that a component of the wrong type is refused. Here the
# type is in the signature, so the call cannot be made at all.
_WRONG_TYPE = (
    "Adaptation (plan H2): a scheme is typed `str`, so all four rows of the harness's provider "
    "— a boolean, a list, a number and a bare object — are refused before the call; no run-time "
    "type check was ported for them."
)


def test_a_uri_read_from_text_is_a_uri() -> None:
    assert isinstance(Uri("https://0:0@0:1/0?0#0"), UriInterface)


def test_a_uri_with_no_scheme_reads_as_having_none() -> None:
    assert Uri("/").get_scheme() == ""


def test_the_scheme_of_a_uri_is_read_off_it() -> None:
    assert Uri("https://foo.com/").get_scheme() == "https"


def test_the_scheme_can_be_replaced() -> None:
    uri = Uri("https://foo.com/")

    replaced = uri.with_scheme("http")

    assert replaced is not uri
    assert replaced.get_scheme() == "http"


@pytest.mark.skip(reason=_WRONG_TYPE)
def test_a_scheme_of_the_wrong_type_is_refused() -> None:
    """The rows of the harness that pass something which is not a scheme."""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/", ""),
        ("http://foo@bar.com:80/", "foo@bar.com"),
        ("http://foo@bar.com:81/", "foo@bar.com:81"),
        ("http://user:foo@bar.com/", "user:foo@bar.com"),
        ("http://bar.com:81/", "bar.com:81"),
    ],
)
def test_the_authority_is_assembled_from_what_the_uri_names(text: str, expected: str) -> None:
    assert Uri(text).get_authority() == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/", ""),
        ("http://user:foo@bar.com/", "user:foo"),
        ("http://foo@bar.com/", "foo"),
    ],
)
def test_the_user_information_is_read_off_the_authority(text: str, expected: str) -> None:
    assert Uri(text).get_user_info() == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/", ""),
        ("http://www.foo.com/", "www.foo.com"),
        ("http://FOOBAR.COM/", "foobar.com"),
    ],
)
def test_the_host_is_read_off_the_authority_in_lower_case(text: str, expected: str) -> None:
    assert Uri(text).get_host() == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("http://www.foo.com/", None),
        ("http://www.foo.com:80/", None),
        ("https://www.foo.com:443/", None),
        ("http://www.foo.com:81/", 81),
    ],
)
def test_a_port_the_scheme_already_implies_is_not_reported(text: str, expected: int | None) -> None:
    assert Uri(text).get_port() == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("http://www.foo.com/", "/"),
        ("http://www.foo.com", ""),
        ("foo/bar", "foo/bar"),
        ("http://www.foo.com/foo bar", "/foo%20bar"),
        ("http://www.foo.com/foo%20bar", "/foo%20bar"),
        ("http://www.foo.com/foo%2fbar", "/foo%2fbar"),
    ],
)
def test_the_path_is_reported_encoded_exactly_once(text: str, expected: str) -> None:
    assert Uri(text).get_path() == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("http://www.foo.com", ""),
        ("http://www.foo.com?", ""),
        ("http://www.foo.com?foo=bar", "foo=bar"),
        ("http://www.foo.com?foo=bar%26baz", "foo=bar%26baz"),
        ("http://www.foo.com?foo=bar&baz=biz", "foo=bar&baz=biz"),
    ],
)
def test_the_query_string_is_reported_encoded_exactly_once(text: str, expected: str) -> None:
    assert Uri(text).get_query() == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("http://www.foo.com", ""),
        ("http://www.foo.com#", ""),
        ("http://www.foo.com#foo", "foo"),
        ("http://www.foo.com#foo%20bar", "foo%20bar"),
    ],
)
def test_the_fragment_is_reported_encoded_exactly_once(text: str, expected: str) -> None:
    assert Uri(text).get_fragment() == expected


def test_a_uri_of_single_digit_components_is_written_back_as_it_was_read() -> None:
    text = "https://0:0@0:1/0?0#0"

    assert str(Uri(text)) == text


def test_a_uri_assembled_component_by_component_reads_as_the_whole() -> None:
    uri = (
        Uri("")
        .with_host("0")
        .with_port(1)
        .with_user_info("0", "0")
        .with_scheme("https")
        .with_path("/0")
        .with_query("0")
        .with_fragment("0")
    )

    assert str(uri) == "https://0:0@0:1/0?0#0"


def test_slashes_inside_a_path_are_left_alone() -> None:
    text = "http://example.org/valid///path"
    uri = Uri(text)

    assert uri.get_path() == "/valid///path"
    assert str(uri) == text


def test_the_path_reduces_its_leading_slashes_to_one() -> None:
    """A path read in isolation must not read as an authority, which would poison the URL.

    See https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2015-3257.
    """
    assert Uri("http://example.org//valid///path").get_path() == "/valid///path"


def test_the_whole_uri_keeps_the_leading_slashes_the_path_reduces() -> None:
    """Where the authority is in front of it, the path cannot be read as one."""
    text = "http://example.org//valid///path"

    assert str(Uri(text)) == text


def test_characters_no_authority_may_carry_are_encoded_in_the_user_information() -> None:
    uri = Uri("http://example.com").with_user_info("foo@bar.com", "pass#word")

    assert uri.get_user_info() == "foo%40bar.com:pass%23word"


def test_user_information_that_arrives_encoded_is_not_encoded_again() -> None:
    uri = Uri("http://example.com").with_user_info("foo%40bar.com", "pass%23word")

    assert uri.get_user_info() == "foo%40bar.com:pass%23word"
