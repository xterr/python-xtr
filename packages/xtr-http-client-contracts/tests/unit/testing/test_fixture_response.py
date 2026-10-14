from __future__ import annotations

import gzip
from dataclasses import replace

from xtr_http_client_contracts.testing._fixture_request import FixtureRequest
from xtr_http_client_contracts.testing._fixture_response import (
    Answer,
    compact,
    compressed,
    head,
    length,
    pretty,
)

REQUEST = FixtureRequest(
    method="GET",
    target="/",
    protocol="HTTP/1.1",
    headers=(),
    body=b"",
    peer=("127.0.0.1", "1234"),
    server_name="127.0.0.1",
    server_port=8000,
)


def test_the_head_answers_in_the_protocol_the_request_came_in() -> None:
    assert head(replace(REQUEST, protocol="HTTP/1.0"), Answer(200)).startswith(b"HTTP/1.0 200 OK")


def test_the_head_names_the_status_it_answers() -> None:
    assert head(REQUEST, Answer(404)).startswith(b"HTTP/1.1 404 Not Found\r\n")


def test_the_head_calls_a_status_nobody_named_unknown() -> None:
    assert head(REQUEST, Answer(599)).startswith(b"HTTP/1.1 599 Unknown\r\n")


def test_the_head_ends_with_the_blank_line_that_opens_the_body() -> None:
    assert head(REQUEST, Answer(200, (("ETag", '"x"'),))) == (
        b'HTTP/1.1 200 OK\r\nETag: "x"\r\nConnection: close\r\n\r\n'
    )


def test_the_head_always_closes_the_connection() -> None:
    assert b"Connection: close\r\n" in head(REQUEST, Answer(200))


def test_pretty_json_is_indented_and_keeps_its_slashes() -> None:
    assert pretty({"REQUEST_URI": "/json/1"}) == b'{\n    "REQUEST_URI": "/json/1"\n}'


def test_compact_json_carries_no_spacing() -> None:
    assert compact({"a": "b", "c": "d"}) == '{"a":"b","c":"d"}'


def test_the_length_header_declares_what_the_body_measures() -> None:
    assert length(b"12345") == ("Content-Length", "5")


def test_a_payload_is_left_alone_when_gzip_was_not_asked_for() -> None:
    body, headers = compressed(REQUEST, b"some text")

    assert body == b"some text"
    assert headers == ()


def test_a_payload_is_gzipped_when_the_request_asked_for_it() -> None:
    asking = replace(REQUEST, headers=(("Accept-Encoding", "deflate, gzip"),))

    body, headers = compressed(asking, b"some text")

    assert gzip.decompress(body) == b"some text"
    assert headers == (("Content-Encoding", "gzip"), ("Vary", "Accept-Encoding"))
