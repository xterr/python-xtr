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
