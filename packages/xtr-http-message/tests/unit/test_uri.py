from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from xtr_http_message_contracts import UriInterface

from xtr_http_message.exception import InvalidArgumentError
from xtr_http_message.uri import Uri

if TYPE_CHECKING:
    from collections.abc import Callable

# Every character a URI carries as it is, in a path, a query string or a fragment.
_UNRESERVED = "a-zA-Z0-9.-_~!$&'()*+,;=:@"


def _components(uri: UriInterface) -> tuple[str, str, str, str, int | None, str, str, str, str]:
    return (
        uri.get_scheme(),
        uri.get_authority(),
        uri.get_user_info(),
        uri.get_host(),
        uri.get_port(),
        uri.get_path(),
        uri.get_query(),
        uri.get_fragment(),
        str(uri),
    )


def _with_scheme(uri: Uri) -> UriInterface:
    return uri.with_scheme("https")


def _with_user_info(uri: Uri) -> UriInterface:
    return uri.with_user_info("user", "pass")


def _with_host(uri: Uri) -> UriInterface:
    return uri.with_host("example.com")


def _with_port(uri: Uri) -> UriInterface:
    return uri.with_port(8080)


def _with_path(uri: Uri) -> UriInterface:
    return uri.with_path("/path/123")


def _with_query(uri: Uri) -> UriInterface:
    return uri.with_query("q=abc")


def _with_fragment(uri: Uri) -> UriInterface:
    return uri.with_fragment("test")


_CHANGES = [
    pytest.param(_with_scheme, id="scheme"),
    pytest.param(_with_user_info, id="user_info"),
    pytest.param(_with_host, id="host"),
    pytest.param(_with_port, id="port"),
    pytest.param(_with_path, id="path"),
    pytest.param(_with_query, id="query"),
    pytest.param(_with_fragment, id="fragment"),
]


def test_uri_is_a_uri() -> None:
    assert UriInterface in Uri.__mro__


def test_parsing_a_full_uri_gives_every_component() -> None:
    uri = Uri("https://user:pass@example.com:8080/path/123?q=abc#test")

    assert _components(uri) == (
        "https",
        "user:pass@example.com:8080",
        "user:pass",
        "example.com",
        8080,
        "/path/123",
        "q=abc",
        "test",
        "https://user:pass@example.com:8080/path/123?q=abc#test",
    )


def test_assembling_a_full_uri_component_by_component() -> None:
    uri = (
        Uri()
        .with_scheme("https")
        .with_user_info("user", "pass")
        .with_host("example.com")
        .with_port(8080)
        .with_path("/path/123")
        .with_query("q=abc")
        .with_fragment("test")
    )

    assert _components(uri) == (
        "https",
        "user:pass@example.com:8080",
        "user:pass",
        "example.com",
        8080,
        "/path/123",
        "q=abc",
        "test",
        "https://user:pass@example.com:8080/path/123?q=abc#test",
    )


def test_user_information_is_encoded_where_it_has_to_be() -> None:
    uri = (
        Uri()
        .with_scheme("https")
        .with_user_info("foo\\user%3D=", "pass%3D=")
        .with_host("example.com")
        .with_port(8080)
        .with_path("/path/123")
        .with_query("q=abc")
        .with_fragment("test")
    )

    assert _components(uri) == (
        "https",
        "foo\\user%3D%3D:pass%3D%3D@example.com:8080",
        "foo\\user%3D%3D:pass%3D%3D",
        "example.com",
        8080,
        "/path/123",
        "q=abc",
        "test",
        "https://foo\\user%3D%3D:pass%3D%3D@example.com:8080/path/123?q=abc#test",
    )


@pytest.mark.parametrize(
    "uri",
    [
        "urn:path-rootless",
        "urn:path:with:colon",
        "urn:/path-absolute",
        "urn:/",
        # only a scheme, with an empty path
        "urn:",
        # only a path
        "/",
        "relative/",
        "0",
        # a reference to the same document
        "",
        # a network path with no scheme
        "//example.org",
        "//example.org/",
        "//example.org?q#h",
        # only a query string
        "?q",
        "?q=abc&foo=bar",
        # only a fragment
        "#fragment",
        # dot segments are not removed for us
        "./foo/../bar",
    ],
)
def test_a_uri_comes_back_as_it_went_in(uri: str) -> None:
    assert str(Uri(uri)) == uri


@pytest.mark.parametrize(
    "uri",
    [
        # RFC 9110 §4.2.1: an `http` URI with an empty host is rejected.
        "http://",
        # RFC 3986 §3.2.2: a colon that no port follows leaves a host that is
        # neither an address in brackets nor a registered name.
        "urn://host:with:colon",
    ],
)
def test_a_string_that_is_not_a_uri_is_refused(uri: str) -> None:
    with pytest.raises(InvalidArgumentError, match=re.escape(f'Unable to parse URI: "{uri}"')):
        _ = Uri(uri)


@pytest.mark.parametrize(
    "uri",
    [
        # RFC 9110 §4.2.1 and §4.2.2: an `http` or `https` URI naming an
        # authority with no host in it is rejected rather than read.
        pytest.param("http://", id="scheme-and-marker"),
        pytest.param("https://", id="another-scheme-and-marker"),
        pytest.param("http://:80/", id="standard-port-no-host"),
        pytest.param("http://:8080/", id="port-no-host"),
        pytest.param("http://:80", id="port-no-host-no-path"),
        # RFC 3986 §3.2.2: a host is an address in brackets or a registered
        # name of unreserved characters, per cent escapes and sub-delimiters,
        # so a colon no port follows is in neither.
        pytest.param("urn://host:with:colon", id="colon-in-host"),
        pytest.param("//example.com:-1", id="negative-port"),
        # RFC 3986 §3.2.3 allows digits; the contract refuses a port outside
        # the sixteen bits a TCP or UDP port is assigned from.
        pytest.param("http://h:65536/", id="port-above-the-range"),
        pytest.param("http://[::1]:65536/", id="port-above-the-range-after-an-address"),
        # RFC 3986 §3.2: an authority is `[ userinfo "@" ] host [ ":" port ]`,
        # so a port belongs to a host. With no host there is no authority to
        # write the port into, and reporting one the text cannot carry would
        # leave a URI contradicting itself.
        pytest.param("//:80", id="port-no-host-no-scheme"),
        pytest.param("foo://:8080/p", id="port-no-host-unknown-scheme"),
        pytest.param("s://:80", id="port-no-host-one-letter-scheme"),
    ],
)
def test_a_refusal_names_the_whole_string_it_was_given(uri: str) -> None:
    with pytest.raises(InvalidArgumentError, match=re.escape(f'Unable to parse URI: "{uri}"')):
        _ = Uri(uri)


@pytest.mark.parametrize(
    ("uri", "path"),
    [
        # RFC 3986 §3.2 and §4.2: an authority may be empty, and a
        # network-path reference naming none is read rather than refused — the
        # rule that an `http` URI needs a host is RFC 9110's, not RFC 3986's.
        pytest.param("//", "", id="marker-alone"),
        pytest.param("///", "/", id="marker-and-a-slash"),
        # RFC 3986 §3.2.3 reads an empty port as no port, so there is nothing
        # here that the missing host would have to carry.
        pytest.param("//:", "", id="marker-and-an-empty-port"),
    ],
)
def test_an_authority_with_no_host_under_no_scheme_is_a_reference(uri: str, path: str) -> None:
    parsed = Uri(uri)

    assert (parsed.get_scheme(), parsed.get_host(), parsed.get_port(), parsed.get_path()) == (
        "",
        "",
        None,
        path,
    )
    # With no host there is no authority to write down, so none is assembled.
    assert (parsed.get_authority(), str(parsed)) == ("", path)


@pytest.mark.parametrize(
    ("uri", "scheme", "host", "path", "text"),
    [
        pytest.param("file:///etc/hosts", "file", "", "/etc/hosts", "file:/etc/hosts", id="rooted"),
        # RFC 3986 §3.3: a path is a path under every scheme, so the colon of
        # a drive letter is a character in it and the slash in front of it
        # stays where it was written.
        pytest.param("FILE:///C:/x", "file", "", "/C:/x", "file:/C:/x", id="drive-letter"),
        pytest.param(
            "file://localhost/etc/hosts",
            "file",
            "localhost",
            "/etc/hosts",
            "file://localhost/etc/hosts",
            id="with-a-host",
        ),
        pytest.param(
            "file:/etc/hosts", "file", "", "/etc/hosts", "file:/etc/hosts", id="one-slash"
        ),
    ],
)
def test_a_local_file_is_a_uri(uri: str, scheme: str, host: str, path: str, text: str) -> None:
    parsed = Uri(uri)

    assert (parsed.get_scheme(), parsed.get_host(), parsed.get_path(), str(parsed)) == (
        scheme,
        host,
        path,
        text,
    )


@pytest.mark.parametrize(
    ("uri", "path", "query", "fragment"),
    [
        pytest.param("http://h/a\nb", "/a%0Ab", "", "", id="newline-in-the-path"),
        pytest.param("http://h/a\rb", "/a%0Db", "", "", id="carriage-return-in-the-path"),
        pytest.param("http://h/p\t", "/p%09", "", "", id="tab-at-the-end-of-the-path"),
        pytest.param("http://h/p\x00", "/p%00", "", "", id="null-in-the-path"),
        pytest.param("http://h/a\x7fb", "/a%7Fb", "", "", id="delete-in-the-path"),
        pytest.param(
            "http://h/p?q\nr#f\ns", "/p", "q%0Ar", "f%0As", id="newlines-in-query-and-fragment"
        ),
    ],
)
def test_a_control_character_is_encoded_rather_than_dropped(
    uri: str, path: str, query: str, fragment: str
) -> None:
    # RFC 3986 §2.1: a character a component may not carry is written as its
    # per cent escape — never deleted, which would answer about another URI.
    parsed = Uri(uri)

    assert (parsed.get_host(), parsed.get_path(), parsed.get_query(), parsed.get_fragment()) == (
        "h",
        path,
        query,
        fragment,
    )


@pytest.mark.parametrize(
    ("uri", "path"),
    [
        pytest.param("  http://h/p  ", "%20%20http://h/p%20%20", id="blanks-around"),
        pytest.param("ht tp://h/", "ht%20tp://h/", id="blank-inside-the-scheme"),
        pytest.param("\xa0http://h/", "%C2%A0http://h/", id="no-break-space-in-front"),
        # RFC 3986 §2.1: the tab is encoded rather than replaced.
        pytest.param("ht\ttp://h/", "ht%09tp://h/", id="tab-inside-the-scheme"),
    ],
)
def test_what_cannot_be_a_scheme_is_the_whole_path(uri: str, path: str) -> None:
    parsed = Uri(uri)

    assert (parsed.get_scheme(), parsed.get_host(), parsed.get_path(), str(parsed)) == (
        "",
        "",
        path,
        path,
    )


def test_a_colon_after_what_cannot_be_a_scheme_stays_inside_the_path() -> None:
    # RFC 3986 §3.1: a scheme opens with a letter, so `0:` is not one and the
    # whole string is the path of a relative reference.
    uri = Uri("0:0")

    assert _components(uri) == ("", "", "", "", None, "0:0", "", "", "0:0")


def test_a_port_above_the_range_is_refused() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match=r"Invalid port: 100000\. Must be between 0 and 65535",
    ):
        _ = Uri().with_port(100_000)


def test_a_negative_port_is_refused() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match=r"Invalid port: -1\. Must be between 0 and 65535",
    ):
        _ = Uri().with_port(-1)


def test_parsing_a_negative_port_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="Unable to parse URI"):
        _ = Uri("//example.com:-1")


def test_port_zero_is_a_port() -> None:
    assert Uri("//example.com:0").get_port() == 0


def test_the_highest_port_of_the_range_is_a_port() -> None:
    assert Uri("//example.com:65535").get_port() == 65535


def test_a_port_written_with_leading_zeros_is_the_number_it_spells() -> None:
    # RFC 3986 §3.2.3: `port = *DIGIT`, and digits spell a number.
    assert Uri("http://example.com:0081/").get_port() == 81


def test_an_empty_port_names_none() -> None:
    # RFC 3986 §3.2.3: a producer omits an empty port, and a reader of one
    # takes it as no port rather than as a zero.
    uri = Uri("//example.com:")

    assert (uri.get_port(), uri.get_authority()) == (None, "example.com")


def test_parsing_a_uri_whose_every_component_is_a_zero() -> None:
    # RFC 3986 §3.1: `0` cannot open a scheme, so nothing in front of the
    # query string is an authority — it is all the path of a relative
    # reference, and the whole string still comes back as it went in.
    uri = Uri("0://0:0@0/0?0#0")

    assert _components(uri) == (
        "",
        "",
        "",
        "",
        None,
        "0://0:0@0/0",
        "0",
        "0",
        "0://0:0@0/0?0#0",
    )


def test_assembling_a_uri_whose_every_component_is_a_zero() -> None:
    uri = (
        Uri()
        .with_scheme("0")
        .with_user_info("0", "0")
        .with_host("0")
        .with_path("/0")
        .with_query("0")
        .with_fragment("0")
    )

    assert _components(uri) == (
        "0",
        "0:0@0",
        "0:0",
        "0",
        None,
        "/0",
        "0",
        "0",
        "0://0:0@0/0?0#0",
    )


def test_a_parsed_scheme_is_lowercased() -> None:
    uri = Uri("HTTP://example.com")

    assert (uri.get_scheme(), str(uri)) == ("http", "http://example.com")


def test_a_scheme_set_afterwards_is_lowercased() -> None:
    uri = Uri("//example.com").with_scheme("HTTP")

    assert (uri.get_scheme(), str(uri)) == ("http", "http://example.com")


def test_a_parsed_host_is_lowercased() -> None:
    uri = Uri("//eXaMpLe.CoM")

    assert (uri.get_host(), str(uri)) == ("example.com", "//example.com")


def test_a_host_set_afterwards_is_lowercased() -> None:
    uri = Uri().with_host("eXaMpLe.CoM")

    assert (uri.get_host(), str(uri)) == ("example.com", "//example.com")


@pytest.mark.parametrize(
    "uri",
    [
        pytest.param(Uri("https://example.com:443"), id="https-parsed"),
        pytest.param(Uri("https://example.com").with_port(443), id="https-set"),
        pytest.param(Uri("http://example.com:80"), id="http-parsed"),
        pytest.param(Uri("http://example.com").with_port(80), id="http-set"),
    ],
)
def test_the_standard_port_of_the_scheme_is_not_worth_reporting(uri: UriInterface) -> None:
    assert (uri.get_port(), uri.get_authority()) == (None, "example.com")


def test_a_port_under_an_unknown_scheme_is_always_worth_reporting() -> None:
    uri = Uri("//example.com").with_port(80)

    assert (uri.get_port(), uri.get_authority()) == (80, "example.com:80")


def test_a_port_stops_being_worth_reporting_when_the_scheme_changes() -> None:
    uri = Uri("http://example.com:443")

    assert (uri.get_port(), uri.with_scheme("https").get_port()) == (443, None)


def test_a_port_can_be_removed() -> None:
    uri = Uri("http://example.com:8080").with_port(None)

    assert (uri.get_port(), str(uri)) == (None, "http://example.com")


def test_user_information_without_a_host_cannot_be_written_down() -> None:
    uri = Uri().with_user_info("user", "pass")

    assert (uri.get_user_info(), uri.get_authority()) == ("user:pass", "")


def test_a_password_without_a_user_is_not_a_user_information() -> None:
    assert Uri().with_user_info("", "pass").get_user_info() == ":pass"


def test_no_password_leaves_the_user_alone() -> None:
    assert Uri().with_user_info("user").get_user_info() == "user"


def test_an_empty_password_leaves_the_user_alone() -> None:
    assert Uri().with_user_info("user", "").get_user_info() == "user"


@pytest.mark.parametrize(
    ("uri", "user_info", "text"),
    [
        # RFC 3986 §3.2.1: `userinfo = *( unreserved / pct-encoded /
        # sub-delims / ":" )`. An `@` or a bracket in it is written as its
        # escape, or the authority it is read back out of would end elsewhere.
        pytest.param("http://u:p@ss@h/", "u:p%40ss", "http://u:p%40ss@h/", id="at-in-password"),
        pytest.param("http://u[x@h/", "u%5Bx", "http://u%5Bx@h/", id="bracket-in-user"),
        # The first colon is the one §3.2.1 keeps, between the user name and
        # what follows it; a later one is data.
        pytest.param("http://u:p:q@h/", "u:p%3Aq", "http://u:p%3Aq@h/", id="a-second-colon"),
        # An escape already written is left exactly as it was written, and a
        # per cent sign that opens none is one.
        pytest.param("http://a%40b@h/", "a%40b", "http://a%40b@h/", id="already-encoded"),
        pytest.param("http://a%zz@h/", "a%25zz", "http://a%25zz@h/", id="broken-escape"),
    ],
)
def test_parsed_user_information_is_encoded_where_it_has_to_be(
    uri: str, user_info: str, text: str
) -> None:
    parsed = Uri(uri)

    assert (parsed.get_user_info(), str(parsed)) == (user_info, text)


@pytest.mark.parametrize(
    "uri",
    [
        pytest.param("http://u:p@ss@h/", id="at-in-password"),
        pytest.param("http://u[x@h/", id="bracket-in-user"),
        pytest.param("http://a%zz@h/", id="broken-escape"),
    ],
)
def test_user_information_survives_a_round_trip_through_the_text(uri: str) -> None:
    # Encoded exactly once, so reading the text back names the very same
    # components — which is what makes `str` a URI rather than a report.
    parsed = Uri(uri)

    assert _components(Uri(str(parsed))) == _components(parsed)


def test_a_broken_escape_in_user_information_set_afterwards_is_encoded() -> None:
    # One filter for user information, whether it was parsed off a URI or
    # handed in: a per cent sign opening no escape is encoded exactly once.
    assert Uri().with_user_info("a%zz").get_user_info() == "a%25zz"


def test_an_escape_in_user_information_set_afterwards_is_not_encoded_again() -> None:
    assert Uri().with_user_info("a%40b").get_user_info() == "a%40b"


@pytest.mark.parametrize(
    ("uri", "path", "query", "fragment", "text"),
    [
        pytest.param(
            "/pa th?q=va lue#frag ment",
            "/pa%20th",
            "q=va%20lue",
            "frag%20ment",
            "/pa%20th?q=va%20lue#frag%20ment",
            id="spaces",
        ),
        pytest.param(
            "/€?€#€",
            "/%E2%82%AC",
            "%E2%82%AC",
            "%E2%82%AC",
            "/%E2%82%AC?%E2%82%AC#%E2%82%AC",
            id="multibyte",
        ),
        pytest.param(
            "/pa%20th?q=va%20lue#frag%20ment",
            "/pa%20th",
            "q=va%20lue",
            "frag%20ment",
            "/pa%20th?q=va%20lue#frag%20ment",
            id="already-encoded",
        ),
        pytest.param(
            "/pa%2-th?q=va%2-lue#frag%2-ment",
            "/pa%252-th",
            "q=va%252-lue",
            "frag%252-ment",
            "/pa%252-th?q=va%252-lue#frag%252-ment",
            id="broken-escape",
        ),
        pytest.param(
            "/pa/th//two?q=va/lue#frag/ment",
            "/pa/th//two",
            "q=va/lue",
            "frag/ment",
            "/pa/th//two?q=va/lue#frag/ment",
            id="segments",
        ),
        pytest.param(
            f"/{_UNRESERVED}?{_UNRESERVED}#{_UNRESERVED}",
            f"/{_UNRESERVED}",
            _UNRESERVED,
            _UNRESERVED,
            f"/{_UNRESERVED}?{_UNRESERVED}#{_UNRESERVED}",
            id="unreserved",
        ),
        pytest.param(
            "/p%61th?q=v%61lue#fr%61gment",
            "/p%61th",
            "q=v%61lue",
            "fr%61gment",
            "/p%61th?q=v%61lue#fr%61gment",
            id="encoded-unreserved",
        ),
    ],
)
def test_components_are_encoded_exactly_once(
    uri: str,
    path: str,
    query: str,
    fragment: str,
    text: str,
) -> None:
    parsed = Uri(uri)

    assert (parsed.get_path(), parsed.get_query(), parsed.get_fragment(), str(parsed)) == (
        path,
        query,
        fragment,
        text,
    )


def test_a_path_set_afterwards_is_encoded() -> None:
    uri = Uri().with_path("/baz?#€/b%61r")

    assert (uri.get_path(), str(uri)) == (
        "/baz%3F%23%E2%82%AC/b%61r",
        "/baz%3F%23%E2%82%AC/b%61r",
    )


def test_a_query_string_set_afterwards_keeps_a_leading_question_mark() -> None:
    uri = Uri().with_query("?=#&€=/&b%61r")

    assert (uri.get_query(), str(uri)) == (
        "?=%23&%E2%82%AC=/&b%61r",
        "??=%23&%E2%82%AC=/&b%61r",
    )


def test_a_fragment_set_afterwards_keeps_a_leading_hash() -> None:
    uri = Uri().with_fragment("#€?/b%61r")

    assert (uri.get_fragment(), str(uri)) == (
        "%23%E2%82%AC?/b%61r",
        "#%23%E2%82%AC?/b%61r",
    )


def test_a_rootless_path_with_no_authority_stays_rootless() -> None:
    uri = Uri().with_path("foo")

    assert (uri.get_path(), str(uri)) == ("foo", "foo")


def test_a_rootless_path_gains_a_slash_once_there_is_a_host() -> None:
    uri = Uri().with_path("foo").with_host("example.com")

    assert (uri.get_path(), str(uri)) == ("/foo", "//example.com/foo")


def test_a_path_opening_with_two_slashes_has_them_reduced_to_one() -> None:
    uri = Uri().with_path("//foo")

    assert (uri.get_path(), str(uri)) == ("/foo", "/foo")


def test_a_path_opening_with_two_slashes_is_kept_when_there_is_an_authority() -> None:
    uri = Uri().with_path("//foo").with_host("example.com")

    assert str(uri) == "//example.com//foo"


def test_a_uri_with_no_component_reads_as_empty_throughout() -> None:
    assert _components(Uri()) == ("", "", "", "", None, "", "", "", "")


@pytest.mark.parametrize("change", _CHANGES)
def test_a_change_leaves_the_instance_it_was_asked_of_alone(
    change: Callable[[Uri], UriInterface],
) -> None:
    uri = Uri()

    assert change(uri) is not uri


@pytest.mark.parametrize("change", _CHANGES)
def test_a_change_that_changes_nothing_hands_the_same_instance_back(
    change: Callable[[Uri], UriInterface],
) -> None:
    uri = Uri("https://user:pass@example.com:8080/path/123?q=abc#test")

    assert change(uri) is uri


def test_a_registered_name_may_carry_a_per_cent_escape() -> None:
    # RFC 3986 §3.2.2: `reg-name = *( unreserved / pct-encoded / sub-delims )`,
    # and an escape already written is left exactly as it was written.
    assert Uri("http://exa%20mple.com/").get_host() == "exa%20mple.com"


@pytest.mark.parametrize(
    "uri",
    [
        pytest.param("//exa mple.com", id="blank"),
        pytest.param("http://exa\tmple.com/", id="tab"),
        pytest.param("http://h\x01/", id="control"),
        pytest.param("http://h\x7f/", id="delete"),
        # A letter outside ASCII is outside the grammar: a name written in
        # another script reaches a host as its ASCII-compatible encoding.
        pytest.param("http://ουτοπία.δπθ.gr/", id="another-script"),
        # A per cent sign that opens no escape.
        pytest.param("http://h%2/", id="broken-escape"),
        pytest.param("http://h%/", id="lone-per-cent"),
        # A bracket anywhere but around an address.
        pytest.param("http://h]x/", id="stray-closing-bracket"),
        pytest.param("http://h[x]/", id="brackets-after-a-name"),
    ],
)
def test_a_registered_name_carrying_anything_else_is_refused(uri: str) -> None:
    # RFC 3986 §3.2.2 says what a registered name may hold; a string holding
    # anything else names no host anybody could look up.
    with pytest.raises(InvalidArgumentError, match=re.escape(f'Unable to parse URI: "{uri}"')):
        _ = Uri(uri)


@pytest.mark.parametrize(
    ("uri", "host", "port"),
    [
        pytest.param("http://[::1]/", "[::1]", None, id="address-only"),
        pytest.param("http://[::1]:8080/", "[::1]", 8080, id="with-a-port"),
        pytest.param("http://[::1]:80/", "[::1]", None, id="with-the-standard-port"),
        pytest.param("http://[::1]:/", "[::1]", None, id="with-an-empty-port"),
    ],
)
def test_an_address_in_brackets_keeps_them(uri: str, host: str, port: int | None) -> None:
    # RFC 3986 §3.2.2 IP-literal, and §3.2.3 — an empty port names none.
    parsed = Uri(uri)

    assert (parsed.get_host(), parsed.get_port()) == (host, port)


@pytest.mark.parametrize(
    "uri",
    [
        # RFC 3986 §3.2.2: an IP-literal is `"[" ( IPv6address / IPvFuture )
        # "]"`, so a bracket nothing closes, a closed one followed by
        # something that is not a port, a pair wrapping nothing or wrapping
        # what is not an address all name no host.
        pytest.param("http://[::1/", id="unclosed"),
        pytest.param("http://[::1]x/", id="trailing-rubbish"),
        pytest.param("http://[]/", id="nothing-between-them"),
        pytest.param("http://[example.com]/", id="a-name-between-them"),
        # An address format that is announced but not defined: RFC 3986 §3.2.2
        # has an application that does not know the version flag report an
        # error rather than guess.
        pytest.param("http://[v7.x]/", id="a-version-flag"),
    ],
)
def test_an_address_in_brackets_that_is_not_one_is_refused(uri: str) -> None:
    with pytest.raises(InvalidArgumentError, match="Unable to parse URI"):
        _ = Uri(uri)


@pytest.mark.parametrize(
    "uri",
    [
        pytest.param("http://[fe80::1%eth0]/", id="a-zone-identifier"),
        pytest.param("http://[fe80::1%25eth0]/", id="an-escaped-zone-identifier"),
        pytest.param("http://[::1%2500]/", id="an-escaped-per-cent-sign"),
    ],
)
def test_an_address_in_brackets_may_not_carry_a_zone_identifier(uri: str) -> None:
    # RFC 3986 §3.2.2: `IP-literal = "[" ( IPv6address / IPvFuture ) "]"`, of
    # which the section says that "this syntax does not support IPv6 scoped
    # addressing zone identifiers". A per cent sign between the brackets can
    # therefore be nothing but a zone identifier or a broken escape, and
    # neither names a host.
    with pytest.raises(InvalidArgumentError, match=re.escape(f'Unable to parse URI: "{uri}"')):
        _ = Uri(uri)


@pytest.mark.parametrize(
    "uri",
    [
        # A bracket inside a path is a character of the path, not a host.
        pytest.param("0://[::1/", id="unclosed"),
        pytest.param("0://[::1]x/", id="trailing-rubbish"),
    ],
)
def test_brackets_under_what_cannot_be_a_scheme_are_path_characters(uri: str) -> None:
    # RFC 3986 §3.1 leaves `0:` out of the scheme grammar, so there is no
    # authority here to hold an address; §2.1 encodes what a path may not
    # carry as it is.
    parsed = Uri(uri)

    assert (parsed.get_scheme(), parsed.get_host()) == ("", "")
    assert parsed.get_path() == uri.replace("[", "%5B").replace("]", "%5D")


def test_a_scheme_must_open_with_a_letter() -> None:
    # RFC 3986 §3.1: `scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )`, so
    # a digit in front leaves a relative reference whose path carries the
    # colon.
    uri = Uri("0:foo")

    assert (uri.get_scheme(), uri.get_path(), str(uri)) == ("", "0:foo", "0:foo")


def test_a_scheme_may_carry_digits_and_the_three_marks_after_its_first_letter() -> None:
    # The rest of RFC 3986 §3.1: a digit, a plus, a hyphen and a full stop.
    uri = Uri("a1+b-c.d:/x")

    assert (uri.get_scheme(), uri.get_path(), str(uri)) == ("a1+b-c.d", "/x", "a1+b-c.d:/x")


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("程式设计.com", id="han"),
        pytest.param("παράδειγμα.δοκιμή", id="greek"),
    ],
)
def test_a_host_set_afterwards_must_be_written_in_ascii(host: str) -> None:
    # RFC 3986 §3.2.2: `reg-name = *( unreserved / pct-encoded / sub-delims )`,
    # every one of them an ASCII character, so a name written in another
    # script reaches a host as its ASCII-compatible `xn--` form. A host handed
    # in is read by the rules that parse one, so `with_host` refuses what
    # `Uri("http://παράδειγμα.δοκιμή")` refuses.
    with pytest.raises(InvalidArgumentError, match=re.escape(f'Invalid host: "{host}"')):
        _ = Uri("http://example.com/").with_host(host)


def test_a_host_in_its_ascii_form_is_assembled_as_it_is() -> None:
    # The `xn--` form of RFC 3986 §3.2.2 is a registered name like any other.
    uri = Uri().with_host("xn--fsqu00a.xn--0zwm56d")

    assert (uri.get_host(), str(uri)) == (
        "xn--fsqu00a.xn--0zwm56d",
        "//xn--fsqu00a.xn--0zwm56d",
    )


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("exa mple.com", id="blank"),
        pytest.param("h\x01", id="control"),
        pytest.param("evil\r\nx-injected: 1", id="line-break"),
        pytest.param("h%2", id="broken-escape"),
        pytest.param("h]x", id="stray-closing-bracket"),
        pytest.param("h:8080", id="a-port-inside-the-host"),
        pytest.param("[::1", id="unclosed-bracket"),
        pytest.param("[]", id="nothing-between-brackets"),
        pytest.param("[example.com]", id="a-name-between-brackets"),
        pytest.param("[v7.x]", id="a-version-flag"),
        pytest.param("[fe80::1%eth0]", id="a-zone-identifier"),
    ],
)
def test_a_host_set_afterwards_is_read_by_the_rules_that_parse_one(host: str) -> None:
    # A `Host` header is written straight from the URI's host, so a host that
    # nothing could have parsed must not reach one by the back door either:
    # RFC 3986 §3.2.2 is read here exactly as it is read off a string.
    with pytest.raises(InvalidArgumentError, match=re.escape(f'Invalid host: "{host}"')):
        _ = Uri().with_host(host)


def test_an_address_in_brackets_may_be_set_afterwards() -> None:
    uri = Uri().with_host("[::1]")

    assert (uri.get_host(), str(uri)) == ("[::1]", "//[::1]")


def test_a_host_can_be_removed() -> None:
    # RFC 3986 §3.2.2 lets an authority name no host, so an empty host is one.
    uri = Uri("http://example.com/p").with_host("")

    assert (uri.get_host(), str(uri)) == ("", "http:/p")
