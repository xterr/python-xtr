from __future__ import annotations

import pytest
from xtr_http_message_contracts import RequestInterface, StreamInterface

from xtr_http_message.exception import InvalidArgumentError
from xtr_http_message.factory.http_factory import HttpFactory
from xtr_http_message.request import Request
from xtr_http_message.uri import Uri

pytestmark = pytest.mark.anyio


def _names_a_header_cannot_carry() -> list[str]:
    """Return a name for every character a header name may not carry.

    Line breaks are spelled out, as the one an attacker reaches for first;
    the rest is every code point the grammar leaves out, each tried on its
    own and inside a name.
    """
    names = [
        "new\nline",
        "new\r\nline",
        "new\rline",
        "new\r\n line",
        "newline\n",
        "\nnewline",
        "newline\r\n",
        "\n\rnewline",
    ]

    for code in range(0x100):
        character = chr(code)
        if character in {"\t", " "} or 0x21 <= code <= 0x7E or code >= 0x80:
            continue
        names.append(f"foo{character}bar")
        names.append(f"foo{character}")

    return names


def test_request_is_a_request() -> None:
    assert RequestInterface in Request.__mro__


def test_a_uri_may_be_given_as_text() -> None:
    assert str(Request("GET", "/").get_uri()) == "/"


def test_a_uri_may_be_given_as_a_uri() -> None:
    uri = Uri("/")

    assert Request("GET", uri).get_uri() is uri


def test_a_uri_that_cannot_be_read_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match='Unable to parse URI: "http://"'):
        _ = Request("GET", "http://")


async def test_a_body_given_to_the_constructor_is_the_body() -> None:
    request = Request("GET", "/", None, b"baz")

    assert (
        isinstance(request.get_body(), StreamInterface),
        await request.get_body().get_contents(),
    ) == (
        True,
        b"baz",
    )


async def test_no_body_given_to_the_constructor_is_an_empty_body() -> None:
    request = Request("GET", "/", None, None)

    assert (
        isinstance(request.get_body(), StreamInterface),
        await request.get_body().get_contents(),
    ) == (
        True,
        b"",
    )


async def test_a_body_of_one_zero_is_still_a_body() -> None:
    assert await Request("GET", "/", None, b"0").get_body().get_contents() == b"0"


def test_the_constructor_does_not_read_the_body_it_is_given() -> None:
    body = HttpFactory().create_stream(b"baz")

    request = Request("GET", "/", None, body)

    assert (request.get_body() is body, body.tell()) == (True, 0)


def test_a_uri_set_afterwards_is_the_uri() -> None:
    request = Request("GET", "/")
    replacement = Uri("http://www.example.com")

    assert request.with_uri(replacement).get_uri() is replacement


def test_setting_a_uri_leaves_the_request_it_was_asked_of_alone() -> None:
    request = Request("GET", "/")
    held = request.get_uri()

    _ = request.with_uri(Uri("http://www.example.com"))

    assert request.get_uri() is held


def test_setting_the_very_uri_it_holds_hands_the_same_request_back() -> None:
    request = Request("GET", "http://foo.com")

    assert request.with_uri(request.get_uri()) is request


def test_setting_an_equal_but_other_uri_gives_a_new_request() -> None:
    request = Request("GET", "/")

    assert request.with_uri(Uri("/")) is not request


def test_a_request_target_set_afterwards_is_the_target() -> None:
    assert Request("GET", "/").with_request_target("*").get_request_target() == "*"


def test_setting_a_request_target_leaves_the_request_it_was_asked_of_alone() -> None:
    request = Request("GET", "/")

    _ = request.with_request_target("*")

    assert request.get_request_target() == "/"


@pytest.mark.parametrize("target", ["foo bar", "/foo bar"])
def test_a_request_target_carrying_whitespace_is_refused(target: str) -> None:
    with pytest.raises(
        InvalidArgumentError,
        match="Invalid request target provided; cannot contain whitespace",
    ):
        _ = Request("GET", "/").with_request_target(target)


@pytest.mark.parametrize(
    ("uri", "target"),
    [
        pytest.param("https://example.net", "/", id="no-path"),
        pytest.param("https://example.net/foo?bar=baz", "/foo?bar=baz", id="path-and-query"),
        pytest.param("https://example.net?bar=baz", "/?bar=baz", id="query-only"),
        pytest.param("", "/", id="nothing"),
        pytest.param("*", "*", id="asterisk"),
        pytest.param("http://foo.com/bar baz/", "/bar%20baz/", id="encoded-path"),
        pytest.param("http://foo.com/baz?bar=bam", "/baz?bar=bam", id="host-path-and-query"),
        pytest.param("http://foo.com/baz?0", "/baz?0", id="query-of-one-zero"),
    ],
)
def test_a_request_target_is_built_from_the_uri(uri: str, target: str) -> None:
    assert Request("GET", uri).get_request_target() == target


def test_the_host_header_is_sent_in_front_of_every_other() -> None:
    request = Request("GET", "http://foo.com/baz?bar=bam", {"Foo": "Bar"})

    assert list(request.get_headers().items()) == [("Host", ["foo.com"]), ("Foo", ["Bar"])]


def test_several_values_under_a_header_read_back_joined_by_commas() -> None:
    request = Request("GET", "http://foo.com/baz?bar=bam", {"Foo": ["a", "b", "c"]})

    assert request.get_header_line("Foo") == "a, b, c"


def test_a_header_the_request_does_not_carry_reads_as_an_empty_line() -> None:
    request = Request("GET", "http://foo.com/baz?bar=bam", {"Foo": ["a", "b", "c"]})

    assert request.get_header_line("Bar") == ""


def test_a_host_header_given_with_the_request_wins_over_the_uri() -> None:
    request = Request("GET", "http://foo.com/baz?bar=bam", {"Host": "a.com"})

    assert request.get_headers() == {"Host": ["a.com"]}


def test_preserving_the_host_keeps_the_header_the_request_carries() -> None:
    request = Request("GET", "http://foo.com/baz?bar=bam", {"Host": "a.com"})

    replaced = request.with_uri(Uri("http://www.foo.com/bar"), preserve_host=True)

    assert replaced.get_header_line("Host") == "a.com"


def test_a_new_uri_takes_the_host_header_with_it() -> None:
    request = Request("GET", "http://foo.com/baz?bar=bam")

    replaced = request.with_uri(Uri("http://www.baz.com/bar"))

    assert (request.get_headers(), replaced.get_header_line("Host")) == (
        {"Host": ["foo.com"]},
        "www.baz.com",
    )


def test_a_header_given_twice_in_different_cases_holds_both_sets_of_values() -> None:
    request = Request("GET", "", {"ZOO": "zoobar", "zoo": ["foobar", "zoobar"]})

    assert request.get_headers() == {"ZOO": ["zoobar", "foobar", "zoobar"]}


def test_a_header_given_twice_reads_back_under_the_case_it_came_in_first() -> None:
    request = Request("GET", "", {"ZOO": "zoobar", "zoo": ["foobar", "zoobar"]})

    assert request.get_header_line("zoo") == "zoobar, foobar, zoobar"


def test_a_header_name_of_digits_is_a_header_name() -> None:
    request = Request("GET", "", {"200": "NumericHeaderValue", "0": "NumericHeaderValueZero"})

    assert request.get_headers() == {
        "200": ["NumericHeaderValue"],
        "0": ["NumericHeaderValueZero"],
    }


@pytest.mark.parametrize(
    ("name", "values", "line"),
    [
        pytest.param("200", ["NumericHeaderValue"], "NumericHeaderValue", id="two-hundred"),
        pytest.param("0", ["NumericHeaderValueZero"], "NumericHeaderValueZero", id="zero"),
    ],
)
def test_a_header_named_with_digits_is_read_back_by_that_name(
    name: str,
    values: list[str],
    line: str,
) -> None:
    request = Request("GET", "", {"200": "NumericHeaderValue", "0": "NumericHeaderValueZero"})

    assert (request.get_header(name), request.get_header_line(name)) == (values, line)


def test_headers_named_with_digits_can_be_set_added_to_and_removed() -> None:
    request = (
        Request("GET", "", {"200": "NumericHeaderValue", "0": "NumericHeaderValueZero"})
        .with_header("300", "NumericHeaderValue2")
        .with_added_header("200", ["A", "B"])
    )

    assert request.get_headers() == {
        "200": ["NumericHeaderValue", "A", "B"],
        "0": ["NumericHeaderValueZero"],
        "300": ["NumericHeaderValue2"],
    }
    assert request.without_header("300").get_headers() == {
        "200": ["NumericHeaderValue", "A", "B"],
        "0": ["NumericHeaderValueZero"],
    }


def test_a_port_the_scheme_does_not_imply_goes_into_the_host_header() -> None:
    assert Request("GET", "http://foo.com:8124/bar").get_header_line("host") == "foo.com:8124"


def test_a_new_uri_replaces_the_port_in_the_host_header() -> None:
    request = Request("GET", "http://foo.com:8124/bar").with_uri(Uri("http://foo.com:8125/bar"))

    assert request.get_header_line("host") == "foo.com:8125"


def test_a_header_with_no_name_is_refused() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match="Header name must be an RFC 7230 compatible string",
    ):
        _ = Request("GET", "https://example.com/").with_header("", "Bar")


def test_a_header_may_hold_an_empty_value() -> None:
    request = Request("GET", "https://example.com/").with_header("Foo", "")

    assert request.get_header("Foo") == [""]


@pytest.mark.parametrize(
    ("uri", "host"),
    [
        pytest.param("https://example.net", "example.net", id="host-only"),
        pytest.param("https://example.net:8080", "example.net:8080", id="with-a-port"),
        pytest.param("https://example.net:443", "example.net", id="with-the-standard-port"),
    ],
)
def test_a_new_uri_sets_the_host_header_on_a_request_that_had_none(uri: str, host: str) -> None:
    request = Request("GET", "/").with_uri(Uri(uri))

    assert request.get_header_line("Host") == host


def test_a_host_header_taken_from_the_uri_is_replaced_by_a_new_uri() -> None:
    request = Request("GET", "https://example.com/")

    assert (
        request.get_header_line("Host"),
        request.with_uri(Uri("https://example.net")).get_header_line("Host"),
    ) == ("example.com", "example.net")


@pytest.mark.parametrize("name", _names_a_header_cannot_carry())
def test_a_header_name_carrying_a_character_it_may_not_is_refused(name: str) -> None:
    with pytest.raises(
        InvalidArgumentError,
        match="Header name must be an RFC 7230 compatible string",
    ):
        _ = Request("GET", "https://example.com/").with_header(name, "Bar")


def test_a_header_value_carrying_a_character_it_may_not_is_refused() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match="Header values must be RFC 7230 compatible strings",
    ):
        _ = Request("GET", "https://example.com/").with_header("Foo", "new\nline")


def test_a_header_value_above_the_byte_range_is_refused() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match="Header values must be RFC 7230 compatible strings",
    ):
        _ = Request("GET", "https://example.com/").with_header("Foo", "€")


def test_one_bad_value_among_several_refuses_the_whole_header() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match="Header values must be RFC 7230 compatible strings",
    ):
        _ = Request("GET", "https://example.com/").with_header("Foo", ["fine", "new\nline"])


def test_a_method_set_afterwards_is_kept_exactly_as_given() -> None:
    assert Request("GET", "/").with_method("pOsT").get_method() == "pOsT"


def test_the_method_given_to_the_constructor_is_the_method() -> None:
    assert Request("POST", "/").get_method() == "POST"


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("evil\r\nX-Injected: 1", id="carriage-return-and-newline"),
        pytest.param("evil\rX-Injected: 1", id="carriage-return"),
        pytest.param("evil\nX-Injected: 1", id="newline"),
    ],
)
def test_a_line_break_in_a_host_cannot_reach_the_host_header(host: str) -> None:
    # The `Host` header is written straight off the URI rather than through
    # the header grammar, so a host carrying a line break would inject a
    # header of its own. RFC 3986 §3.2.2 leaves CR and LF out of a registered
    # name, and a host handed to `with_host` is read by that same rule.
    request = Request("GET", "http://foo.com/")

    with pytest.raises(InvalidArgumentError, match="Invalid host"):
        _ = request.with_uri(request.get_uri().with_host(host))


@pytest.mark.parametrize(
    "uri",
    [
        pytest.param("http://evil\r\nX-Injected: 1/", id="carriage-return-and-newline"),
        pytest.param("http://evil\rX-Injected: 1/", id="carriage-return"),
        pytest.param("http://evil\nX-Injected: 1/", id="newline"),
    ],
)
def test_a_line_break_in_a_parsed_host_cannot_reach_the_host_header(uri: str) -> None:
    # The same rule read off a string: nothing is trimmed and no character is
    # dropped, so the URI is refused rather than cleaned up into one that
    # would carry a second header.
    with pytest.raises(InvalidArgumentError, match="Unable to parse URI"):
        _ = Request("GET", uri)
