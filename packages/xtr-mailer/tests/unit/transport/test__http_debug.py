"""What an HTTP exchange is logged as, with nothing in it that could be a credential."""

from __future__ import annotations

import pytest

from xtr_mailer.transport._http_debug import http_debug


def _info(url: str = "https://api.example.com/v3/messages", *lines: object) -> dict[str, object]:
    return {"http_method": "POST", "url": url, "response_headers": list(lines)}


def test_the_request_and_every_line_of_the_answer_are_logged() -> None:
    info = _info("https://api.example.com/v3/messages", "HTTP/1.1 200 OK", "Content-Length: 2")

    assert http_debug(info) == (
        "> POST https://api.example.com/v3/messages\n< HTTP/1.1 200 OK\n< Content-Length: 2\n"
    )


def test_the_user_info_and_the_query_of_the_url_are_left_out() -> None:
    info = _info("https://api:key-secret@api.example.com:8443/send?key=secret#part")

    assert http_debug(info) == "> POST https://api.example.com:8443/send\n"


@pytest.mark.parametrize("name", ["Set-Cookie", "cookie", "Authorization", "Proxy-Authorization"])
def test_a_header_that_may_carry_a_credential_is_redacted(name: str) -> None:
    debug = http_debug(_info("https://api.example.com/", f"{name}: session=secret"))

    assert debug.endswith(f"< {name}: [redacted]\n")
    assert "secret" not in debug


@pytest.mark.parametrize(
    "name",
    [
        "WWW-Authenticate",
        "Proxy-Authenticate",
        "Authentication-Info",
        "Proxy-Authentication-Info",
        "Set-Cookie2",
        "X-Api-Key",
        "x-auth-token",
        "X-Client-SECRET",
        "X-Signing-Key",
        "X-Session-Id",
        "X-Cookie-Jar",
    ],
)
def test_every_header_named_after_a_credential_is_redacted(name: str) -> None:
    line = f'{name}: Bearer realm="api", token="secret"'

    debug = http_debug(_info("https://api.example.com/", line))

    assert debug.endswith(f"< {name}: [redacted]\n")
    assert "secret" not in debug


@pytest.mark.parametrize(
    ("line", "shown"),
    [
        pytest.param(
            "Location: https://api.example.com/next?key=secret#part",
            "Location: https://api.example.com/next",
            id="location",
        ),
        pytest.param("location: /next?key=secret", "location: /next", id="relative-location"),
        pytest.param(
            "Content-Location: https://api:secret@api.example.com/m?x=1",
            "Content-Location: https://api.example.com/m",
            id="content-location",
        ),
        pytest.param(
            "Refresh: 5; URL=https://api.example.com/r;v=1?key=secret",
            "Refresh: 5; URL=https://api.example.com/r;v=1",
            id="refresh",
        ),
        pytest.param("Refresh: 0; url=/r?key=secret", "Refresh: 0; url=/r", id="relative-refresh"),
        pytest.param(
            "Link: </page?token=secret>; rel=next",
            "Link: </page>; rel=next",
            id="link",
        ),
        pytest.param(
            "X-Debug: see http://api:secret@api.example.com/x?a=secret for more",
            "X-Debug: see http://api.example.com/x for more",
            id="url-in-text",
        ),
    ],
)
def test_a_url_an_answer_carries_loses_its_user_info_and_query(line: str, shown: str) -> None:
    debug = http_debug(_info("https://api.example.com/", line))

    assert debug.endswith(f"< {shown}\n")
    assert "secret" not in debug


@pytest.mark.parametrize(
    ("line", "shown"),
    [
        pytest.param("\r\nSet-Cookie: x", "\\r\\nSet-Cookie: [redacted]", id="line-break"),
        pytest.param("\u2028X-Note: a", "\\u2028X-Note: a", id="line-separator"),
    ],
)
def test_a_control_character_in_a_header_name_is_shown_escaped(line: str, shown: str) -> None:
    debug = http_debug(_info("https://api.example.com/", line))

    assert debug == f"> POST https://api.example.com/\n< {shown}\n"


def test_a_long_answer_is_cut_to_its_first_hundred_lines() -> None:
    lines = [f"X-Line: {number}" for number in range(250)]

    debug = http_debug(_info("https://api.example.com/", *lines))

    assert debug.count("\n< ") == 101
    assert debug.endswith("< X-Line: 99\n< … 150 more lines\n")


def test_a_control_character_in_an_answer_is_shown_escaped() -> None:
    debug = http_debug(_info("https://api.example.com/", "X-Reason: a\r\nb\x00c"))

    assert debug.endswith("< X-Reason: a\\r\\nb\\x00c\n")


def test_a_long_line_of_an_answer_is_cut_short() -> None:
    debug = http_debug(_info("https://api.example.com/", "X-Long: " + "a" * 2000))

    assert debug.endswith("< X-Long: " + "a" * 992 + "…\n")


def test_a_url_that_cannot_be_read_is_not_shown() -> None:
    assert http_debug(_info("https://[::1/send")) == "> POST [unreadable URL]\n"


@pytest.mark.parametrize(
    "info",
    [
        pytest.param({}, id="nothing"),
        pytest.param(None, id="not-a-mapping"),
        pytest.param({"http_method": 1, "url": None, "response_headers": "HTTP/1.1"}, id="wrong"),
    ],
)
def test_what_the_transfer_does_not_know_is_left_out(info: object) -> None:
    assert http_debug(info) == ""


def test_a_line_that_is_not_text_is_left_out() -> None:
    assert http_debug(_info("https://api.example.com/", b"HTTP/1.1 200 OK", 7)) == (
        "> POST https://api.example.com/\n"
    )
