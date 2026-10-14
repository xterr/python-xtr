from __future__ import annotations

import gzip
import time

import pytest

from .conftest import exchange, serving_port

pytestmark = pytest.mark.usefixtures("server")

HOST_HEAD = b"Host: 127.0.0.1\r\n"
SLOW = 0.25


def test_the_root_answers_the_variables_uncompressed() -> None:
    raw = exchange(b"GET / HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_code == 200
    assert raw.header("content-type") == "application/json"
    assert raw.header("content-encoding") is None
    assert raw.header("vary") is None
    assert raw.json_body()["REQUEST_URI"] == "/"


def test_the_root_compresses_when_the_request_accepts_gzip() -> None:
    raw = exchange(b"GET / HTTP/1.1\r\n" + HOST_HEAD + b"Accept-Encoding: gzip\r\n\r\n")

    assert raw.header("content-encoding") == "gzip"
    assert raw.header("vary") == "Accept-Encoding"
    assert b'"REQUEST_URI": "/"' in gzip.decompress(raw.body)


def test_an_absolute_request_target_routes_on_its_path() -> None:
    raw = exchange(b"GET http://127.0.0.1/ HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_code == 200
    assert raw.json_body()["REQUEST_URI"] == "http://127.0.0.1/"


def test_head_sends_the_length_of_the_body_it_withholds() -> None:
    raw = exchange(b"HEAD /head HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.body == b""
    assert raw.header("content-length") is not None
    assert int(raw.header("content-length") or "0") > 0
    assert '"REQUEST_METHOD":"HEAD"' in (raw.header("x-request-vars") or "")


def test_head_answers_a_body_to_any_other_method() -> None:
    raw = exchange(b"GET /head HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert len(raw.body) == int(raw.header("content-length") or "0")
    assert raw.json_body()["REQUEST_URI"] == "/head"


def test_early_hints_arrive_before_the_answer() -> None:
    raw = exchange(b"GET /103 HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.raw == (
        b"HTTP/1.1 103 Early Hints\r\n"
        b"Link: </style.css>; rel=preload; as=style\r\n"
        b"Link: </script.js>; rel=preload; as=script\r\n"
        b"\r\n"
        b"HTTP/1.1 200 OK\r\n"
        b"Date: Fri, 26 May 2017 10:02:11 GMT\r\n"
        b"Content-Length: 13\r\n"
        b"\r\n"
        b"Here the body"
    )


def test_not_found_answers_the_variables() -> None:
    raw = exchange(b"GET /404 HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_line == "HTTP/1.1 404 Not Found"
    assert raw.header("content-type") == "application/json"
    assert raw.json_body()["REQUEST_URI"] == "/404"


def test_the_gzipped_not_found_sends_its_head_first() -> None:
    started = time.monotonic()
    raw = exchange(b"GET /404-gzipped HTTP/1.1\r\n" + HOST_HEAD + b"\r\n", min_bytes=1)

    assert time.monotonic() - started < SLOW
    assert raw.status_code == 404
    assert raw.header("content-type") == "text/plain"


def test_the_gzipped_not_found_sends_its_body_late() -> None:
    started = time.monotonic()
    raw = exchange(b"GET /404-gzipped HTTP/1.1\r\n" + HOST_HEAD + b"Accept-Encoding: gzip\r\n\r\n")

    assert time.monotonic() - started >= SLOW
    assert raw.header("content-encoding") == "gzip"
    assert gzip.decompress(raw.body) == b"some text"


def test_the_permanent_redirect_needs_the_expected_credentials() -> None:
    raw = exchange(
        b"GET /301 HTTP/1.1\r\n" + HOST_HEAD + b"Authorization: Basic Zm9vOmJhcg==\r\n\r\n"
    )

    assert raw.status_line == "HTTP/1.1 301 Moved Permanently"
    assert raw.header("location") == f"http://127.0.0.1:{serving_port()}/302"


def test_the_permanent_redirect_answers_the_variables_without_them() -> None:
    raw = exchange(b"GET /301 HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_code == 200
    assert raw.header("location") is None


def test_the_bad_tld_redirect_points_at_an_unresolvable_host() -> None:
    raw = exchange(b"GET /301/bad-tld HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_code == 301
    assert raw.header("location") == "http://foo.example."


def test_the_invalid_redirect_points_at_an_unparsable_target() -> None:
    raw = exchange(b"GET /301/invalid HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_code == 301
    assert raw.header("location") == "//?foo=bar"


@pytest.mark.parametrize(
    "target",
    [b"/301/proxy", b"http://localhost/301/proxy", b"http://127.0.0.1/301/proxy"],
)
def test_the_proxy_redirect_points_at_the_root(target: bytes) -> None:
    raw = exchange(b"GET " + target + b" HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_code == 301
    assert raw.header("location") == f"http://localhost:{serving_port()}/"


def test_the_found_redirect_points_at_the_root_by_default() -> None:
    raw = exchange(b"GET /302 HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_line == "HTTP/1.1 302 Found"
    assert raw.header("location") == f"http://localhost:{serving_port()}/"


def test_the_found_redirect_takes_its_target_from_the_query() -> None:
    raw = exchange(b"GET /302?location=/301 HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.header("location") == "/301"


def test_the_found_redirect_stops_redirecting_once_authorized() -> None:
    raw = exchange(b"GET /302 HTTP/1.1\r\n" + HOST_HEAD + b"Authorization: Basic eA==\r\n\r\n")

    assert raw.status_code == 200
    assert raw.header("location") is None


def test_the_relative_redirect_points_one_level_up() -> None:
    raw = exchange(b"GET /302/relative HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_code == 302
    assert raw.header("location") == ".."


def test_not_modified_declares_more_than_it_sends() -> None:
    raw = exchange(b"GET /304 HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_line == "HTTP/1.1 304 Not Modified"
    assert raw.header("content-length") == "10"
    assert raw.body == b"12345"


def test_the_etag_route_answers_the_variables_when_nothing_is_cached() -> None:
    raw = exchange(b"GET /304/etag HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_code == 200
    assert raw.header("etag") == '"abc123"'
    assert raw.json_body()["REQUEST_URI"] == "/304/etag"


def test_the_etag_route_answers_not_modified_to_a_matching_request() -> None:
    raw = exchange(b"GET /304/etag HTTP/1.1\r\n" + HOST_HEAD + b'If-None-Match: "abc123"\r\n\r\n')

    assert raw.status_code == 304
    assert raw.header("etag") == '"abc123"'
    assert raw.body == b""


def test_the_temporary_redirect_points_at_the_echo() -> None:
    raw = exchange(b"GET /307 HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_line == "HTTP/1.1 307 Temporary Redirect"
    assert raw.header("location") == f"http://localhost:{serving_port()}/post"


def test_the_broken_length_declares_more_than_it_sends() -> None:
    raw = exchange(b"GET /length-broken HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.header("content-length") == "1000"
    assert 0 < len(raw.body) < 1000


def test_the_echo_answers_the_fields_of_a_form() -> None:
    raw = exchange(
        b"POST /post HTTP/1.1\r\n" + HOST_HEAD + b"Content-Type: application/x-www-form-urlencoded"
        b"\r\nContent-Length: 15\r\n\r\nfoo=bar&baz=qux"
    )

    assert raw.header("content-type") == "application/json"
    assert raw.header("content-length") == str(len(raw.body))
    assert raw.json_body() == {"foo": "bar", "baz": "qux", "REQUEST_METHOD": "POST"}


def test_the_echo_answers_the_keys_of_a_json_body_and_its_content_type() -> None:
    raw = exchange(
        b"POST /post HTTP/1.1\r\n" + HOST_HEAD + b"Content-Type: application/json\r\n"
        b'Content-Length: 13\r\n\r\n{"foo":"bar"}'
    )

    assert raw.json_body() == {
        "foo": "bar",
        "content-type": "application/json",
        "REQUEST_METHOD": "POST",
    }


def test_the_echo_answers_an_unknown_content_type_for_an_empty_body() -> None:
    raw = exchange(b"GET /post HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.json_body() == {"content-type": "?", "REQUEST_METHOD": "GET"}


def test_the_echo_lets_a_form_field_shadow_the_method() -> None:
    raw = exchange(
        b"POST /post HTTP/1.1\r\n" + HOST_HEAD + b"Content-Type: application/x-www-form-urlencoded"
        b"\r\nContent-Length: 18\r\n\r\nREQUEST_METHOD=PUT"
    )

    assert raw.json_body() == {"REQUEST_METHOD": "PUT"}


def test_the_header_timeout_waits_before_answering_at_all() -> None:
    started = time.monotonic()
    raw = exchange(b"GET /timeout-header HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert time.monotonic() - started >= SLOW
    assert raw.status_code == 200


def test_the_body_timeout_sends_its_head_and_first_chunk_at_once() -> None:
    started = time.monotonic()
    raw = exchange(b"GET /timeout-body HTTP/1.1\r\n" + HOST_HEAD + b"\r\n", min_bytes=1)

    assert time.monotonic() - started < SLOW
    assert raw.body == b"<1>"


def test_the_body_timeout_waits_before_its_second_chunk() -> None:
    started = time.monotonic()
    raw = exchange(b"GET /timeout-body HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert time.monotonic() - started >= SLOW
    assert raw.body == b"<1><2>"


def test_the_long_timeout_says_nothing_for_a_second() -> None:
    started = time.monotonic()
    raw = exchange(b"GET /timeout-long HTTP/1.1\r\n" + HOST_HEAD + b"\r\n", min_bytes=1)

    assert time.monotonic() - started >= 1.0
    assert b"<1>" in raw.raw


def test_the_chunked_route_frames_its_body_in_three_chunks() -> None:
    raw = exchange(b"GET /chunked HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.header("transfer-encoding") == "chunked"
    assert raw.body == b"8\r\nchunked \r\n5\r\ndata \r\n6\r\nworks!\r\n0\r\n\r\n"


def test_the_broken_chunked_route_stops_inside_a_chunk() -> None:
    raw = exchange(b"GET /chunked-broken HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.header("transfer-encoding") == "chunked"
    assert raw.body == b"8\r\nchunked \r\n5\r\ndata \r\n6\r\nw"


def test_the_broken_gzip_route_announces_what_it_does_not_send() -> None:
    raw = exchange(b"GET /gzip-broken HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.header("content-encoding") == "gzip"
    assert raw.body == b"-" * 1000


def test_the_endless_route_starts_answering_at_once() -> None:
    started = time.monotonic()
    raw = exchange(b"GET /max-duration HTTP/1.1\r\n" + HOST_HEAD + b"\r\n", min_bytes=1)

    assert time.monotonic() - started < SLOW
    assert b"<1>" in raw.raw


def test_the_json_route_answers_three_documents() -> None:
    raw = exchange(b"GET /json HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.header("content-type") == "application/json"
    assert raw.json_body() == {
        "documents": [{"id": "/json/1"}, {"id": "/json/2"}, {"id": "/json/3"}]
    }


@pytest.mark.parametrize("number", [1, 2, 3])
def test_a_json_document_answers_its_own_target_as_a_title(number: int) -> None:
    target = f"/json/{number}".encode()
    raw = exchange(b"GET " + target + b" HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.json_body() == {"title": target.decode()}


def test_the_custom_route_answers_the_status_it_is_given() -> None:
    raw = exchange(b"GET /custom?status=404 HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_line == "HTTP/1.1 404 Not Found"
    assert raw.json_body()["REQUEST_URI"] == "/custom?status=404"


def test_the_custom_route_ignores_a_status_that_is_not_a_number() -> None:
    raw = exchange(b"GET /custom?status=nope HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_code == 200


def test_the_custom_route_sends_the_headers_it_is_given() -> None:
    raw = exchange(
        b"GET /custom?headers[]=Foo:%20bar&headers[]=Baz:%20qux HTTP/1.1\r\n" + HOST_HEAD + b"\r\n"
    )

    assert raw.header("foo") == "bar"
    assert raw.header("baz") == "qux"


def test_the_custom_route_keeps_answering_json() -> None:
    raw = exchange(
        b"GET /custom?headers[]=Content-Type:%20text/plain HTTP/1.1\r\n" + HOST_HEAD + b"\r\n"
    )

    assert raw.header_values("content-type") == ["application/json"]


def test_an_unknown_path_answers_nothing_at_all() -> None:
    raw = exchange(b"GET /nowhere HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.status_line == "HTTP/1.1 200 OK"
    assert raw.header("content-length") == "0"
    assert raw.body == b""


def test_every_answer_closes_the_connection() -> None:
    raw = exchange(b"GET /404 HTTP/1.1\r\n" + HOST_HEAD + b"\r\n")

    assert raw.header("connection") == "close"
