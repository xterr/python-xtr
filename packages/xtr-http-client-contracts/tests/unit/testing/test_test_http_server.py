from __future__ import annotations

import socket

import pytest

from xtr_http_client_contracts.testing import TestHttpServer

from .conftest import HOST, PORT, exchange, is_listening


def test_it_is_not_collected_as_a_test_case() -> None:
    assert TestHttpServer.__test__ is False


def test_it_reports_where_it_listens() -> None:
    server = TestHttpServer()

    assert server.host == "127.0.0.1"
    assert server.port == 8057
    assert server.base_uri == "http://127.0.0.1:8057"


def test_it_answers_once_started() -> None:
    server = TestHttpServer()
    server.start()
    try:
        assert exchange(b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n\r\n").status_code == 404
    finally:
        server.stop()


def test_a_second_start_is_a_no_op() -> None:
    server = TestHttpServer()
    server.start()
    try:
        server.start()

        assert exchange(b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n\r\n").status_code == 404
    finally:
        server.stop()


def test_it_frees_the_port_when_stopped() -> None:
    server = TestHttpServer()
    server.start()
    server.stop()

    assert is_listening() is False


def test_a_second_stop_is_a_no_op() -> None:
    server = TestHttpServer()
    server.start()
    server.stop()

    server.stop()

    assert is_listening() is False


def test_it_can_be_started_again_after_being_stopped() -> None:
    server = TestHttpServer()
    server.start()
    server.stop()

    server.start()
    try:
        assert exchange(b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1:8057\r\n\r\n").status_code == 404
    finally:
        server.stop()


def test_it_stops_when_a_stopped_server_was_never_started() -> None:
    TestHttpServer().stop()

    assert is_listening() is False


def test_it_stops_on_a_connection_that_asked_for_nothing() -> None:
    server = TestHttpServer()
    server.start()

    with socket.create_connection((HOST, PORT), timeout=5.0):
        server.stop()

    assert is_listening() is False


def test_it_runs_for_the_length_of_a_with_block() -> None:
    with TestHttpServer():
        assert is_listening() is True

    assert is_listening() is False


def test_it_raises_whatever_stopped_it_from_listening() -> None:
    blocked = TestHttpServer()

    with TestHttpServer(), pytest.raises(OSError, match="address already in use"):
        blocked.start()

    blocked.start()
    try:
        assert is_listening() is True
    finally:
        blocked.stop()


def test_it_listens_where_it_is_told_to() -> None:
    with TestHttpServer(host="127.0.0.1", port=8058) as server:
        assert server.base_uri == "http://127.0.0.1:8058"
        assert is_listening() is False
