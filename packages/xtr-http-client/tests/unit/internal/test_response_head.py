from __future__ import annotations

from xtr_http_client.internal.response_head import ResponseHead


def test_it_starts_out_with_nothing_but_a_protocol_version() -> None:
    head = ResponseHead()

    assert head.protocol_version == "1.1"
    assert head.status_code == 0
    assert head.reason_phrase == ""
    assert head.headers == {}
    assert head.recorded == []


def test_a_status_line_gives_the_version_the_code_and_the_reason() -> None:
    head = ResponseHead()

    head.add_line("HTTP/1.0 404 Not Found")

    assert head.protocol_version == "1.0"
    assert head.status_code == 404
    assert head.reason_phrase == "Not Found"


def test_a_status_line_with_no_reason_leaves_it_empty() -> None:
    head = ResponseHead()

    head.add_line("HTTP/2 204")

    assert head.protocol_version == "2"
    assert head.status_code == 204
    assert head.reason_phrase == ""


def test_a_header_is_found_under_its_lowered_name() -> None:
    head = ResponseHead()

    head.add_line("Content-Type: text/plain")

    assert head.headers == {"content-type": ["text/plain"]}


def test_a_header_sent_twice_stays_twice() -> None:
    head = ResponseHead()

    head.add_line("Set-Cookie: a=1")
    head.add_line("set-cookie: b=2")

    assert head.headers == {"set-cookie": ["a=1", "b=2"]}


def test_a_value_with_no_space_after_the_colon_reads_the_same() -> None:
    head = ResponseHead()

    head.add_line("Age:0")

    assert head.headers == {"age": ["0"]}


def test_a_value_carrying_a_colon_keeps_it() -> None:
    head = ResponseHead()

    head.add_line("Location: https://example.com/next")

    assert head.headers == {"location": ["https://example.com/next"]}


def test_a_second_status_line_drops_the_headers_of_the_first() -> None:
    head = ResponseHead()

    head.add_line("HTTP/1.1 301 Moved Permanently")
    head.add_line("Location: https://example.com/next")
    head.add_line("HTTP/1.1 200 OK")
    head.add_line("Content-Type: text/plain")

    assert head.status_code == 200
    assert head.headers == {"content-type": ["text/plain"]}


def test_every_line_seen_is_recorded_in_the_order_it_arrived() -> None:
    head = ResponseHead()

    head.add_line("HTTP/1.1 301 Moved Permanently\r\n")
    head.add_line("Location: https://example.com/next\r\n")
    head.add_line("HTTP/1.1 200 OK\r\n")

    assert head.recorded == [
        "HTTP/1.1 301 Moved Permanently",
        "Location: https://example.com/next",
        "HTTP/1.1 200 OK",
    ]


def test_a_line_that_is_neither_is_recorded_and_otherwise_ignored() -> None:
    head = ResponseHead()

    head.add_line("HTTP/1.1 200 OK")
    head.add_line("garbage")

    assert head.status_code == 200
    assert head.headers == {}
    assert head.recorded == ["HTTP/1.1 200 OK", "garbage"]


def test_a_line_starting_with_the_protocol_but_not_a_status_is_not_one() -> None:
    head = ResponseHead()

    head.add_line("HTTP/1.1 200 OK")
    head.add_line("Content-Type: text/plain")
    head.add_line("HTTP/1.1 nonsense")

    assert head.status_code == 200
    assert head.headers == {"content-type": ["text/plain"]}


def test_a_copy_carries_everything_the_original_had() -> None:
    head = ResponseHead()
    head.add_line("HTTP/1.1 200 OK")
    head.add_line("Content-Type: text/plain")

    copied = head.copy()

    assert copied.protocol_version == "1.1"
    assert copied.status_code == 200
    assert copied.reason_phrase == "OK"
    assert copied.headers == {"content-type": ["text/plain"]}
    assert copied.recorded == head.recorded


def test_a_copy_can_be_changed_without_touching_the_original() -> None:
    head = ResponseHead()
    head.add_line("HTTP/1.1 200 OK")
    head.add_line("Set-Cookie: a=1")

    copied = head.copy()
    copied.add_line("Set-Cookie: b=2")
    copied.status_code = 418

    assert head.headers == {"set-cookie": ["a=1"]}
    assert head.status_code == 200
    assert copied.headers == {"set-cookie": ["a=1", "b=2"]}
