from __future__ import annotations

import pytest

from .conftest import exchange

pytestmark = pytest.mark.usefixtures("server")


def test_it_echoes_the_fixed_variables_before_the_headers() -> None:
    body = exchange(b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n\r\n").json_body()

    assert list(body) == [
        "SERVER_PROTOCOL",
        "SERVER_NAME",
        "REQUEST_URI",
        "REQUEST_METHOD",
        "REMOTE_ADDR",
        "REMOTE_PORT",
        "HTTP_HOST",
    ]


def test_it_pretty_prints_the_variables() -> None:
    raw = exchange(b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n\r\n")

    assert raw.body.startswith(b'{\n    "SERVER_PROTOCOL": "HTTP/1.1",\n')


def test_it_echoes_the_version_the_request_came_in() -> None:
    raw = exchange(b"GET /404 HTTP/1.0\r\nHost: 127.0.0.1:8057\r\n\r\n")

    assert raw.status_line == "HTTP/1.0 404 Not Found"
    assert raw.json_body()["SERVER_PROTOCOL"] == "HTTP/1.0"


def test_it_echoes_the_raw_request_target() -> None:
    body = exchange(b"GET /?a=a&b=b HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n\r\n").json_body()

    assert body["REQUEST_URI"] == "/?a=a&b=b"


def test_it_echoes_an_absolute_request_target_whole() -> None:
    body = exchange(
        b"GET http://localhost:8057/ HTTP/1.1\r\nHost: localhost:8057\r\n\r\n"
    ).json_body()

    assert body["REQUEST_URI"] == "http://localhost:8057/"


def test_it_echoes_the_host_it_is_bound_to_as_the_server_name() -> None:
    body = exchange(b"GET /404 HTTP/1.1\r\nHost: localhost:8057\r\n\r\n").json_body()

    assert body["SERVER_NAME"] == "127.0.0.1"
    assert body["HTTP_HOST"] == "localhost:8057"


def test_it_echoes_the_address_and_port_the_request_came_from() -> None:
    raw = exchange(b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n\r\n")

    assert raw.json_body()["REMOTE_ADDR"] == "127.0.0.1"
    assert raw.json_body()["REMOTE_PORT"] == str(raw.local_port)


def test_it_echoes_the_method() -> None:
    body = exchange(b"DELETE /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n\r\n").json_body()

    assert body["REQUEST_METHOD"] == "DELETE"


def test_it_upper_cases_header_names_and_replaces_dashes() -> None:
    body = exchange(
        b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\nX-Foo-Bar: baz\r\n\r\n"
    ).json_body()

    assert body["HTTP_X_FOO_BAR"] == "baz"


def test_it_joins_a_header_sent_twice() -> None:
    body = exchange(
        b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\nX-Foo: one\r\nX-Foo: two\r\n\r\n"
    ).json_body()

    assert body["HTTP_X_FOO"] == "one, two"


def test_it_echoes_the_body_headers_too() -> None:
    body = exchange(
        b"POST /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n"
        b"Content-Type: text/plain\r\nContent-Length: 2\r\n\r\nhi"
    ).json_body()

    assert body["HTTP_CONTENT_TYPE"] == "text/plain"
    assert body["HTTP_CONTENT_LENGTH"] == "2"


def test_it_decodes_basic_credentials() -> None:
    body = exchange(
        b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n"
        b"Authorization: Basic Zm9vOmJhcj1iYXI=\r\n\r\n"
    ).json_body()

    assert body["AUTH_USER"] == "foo"
    assert body["AUTH_PW"] == "bar=bar"
    assert body["HTTP_AUTHORIZATION"] == "Basic Zm9vOmJhcj1iYXI="


def test_it_omits_the_credentials_when_none_were_sent() -> None:
    body = exchange(b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n\r\n").json_body()

    assert "AUTH_USER" not in body
    assert "AUTH_PW" not in body


def test_it_omits_the_credentials_when_the_scheme_is_not_basic() -> None:
    body = exchange(
        b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\nAuthorization: Bearer token\r\n\r\n"
    ).json_body()

    assert "AUTH_USER" not in body
    assert body["HTTP_AUTHORIZATION"] == "Bearer token"


def test_it_omits_the_credentials_when_they_do_not_decode() -> None:
    body = exchange(
        b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\nAuthorization: Basic !!!!\r\n\r\n"
    ).json_body()

    assert "AUTH_USER" not in body


def test_it_omits_the_credentials_when_they_carry_no_colon() -> None:
    body = exchange(
        b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\nAuthorization: Basic Zm9v\r\n\r\n"
    ).json_body()

    assert "AUTH_USER" not in body


def test_it_reads_a_body_sent_in_chunks() -> None:
    body = exchange(
        b"POST /post HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n"
        b"Content-Type: application/x-www-form-urlencoded\r\n"
        b"Transfer-Encoding: chunked\r\n\r\n"
        b"5\r\nfoo=b\r\n2\r\nar\r\n0\r\n\r\n"
    ).json_body()

    assert body["foo"] == "bar"


def test_it_answers_nothing_to_a_connection_that_sends_nothing() -> None:
    assert exchange(b"").raw == b""


def test_it_answers_nothing_to_a_request_line_it_cannot_read() -> None:
    assert exchange(b"not a request line\r\n\r\n").raw == b""
