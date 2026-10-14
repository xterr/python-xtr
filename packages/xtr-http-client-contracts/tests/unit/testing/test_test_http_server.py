from __future__ import annotations

import socket

import pytest

from xtr_http_client_contracts.testing import TestHttpServer

from .conftest import HOST, exchange, is_listening

NOT_FOUND = b"GET /404 HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"


def test_it_is_not_collected_as_a_test_case() -> None:
    assert TestHttpServer.__test__ is False


def test_it_has_no_port_before_it_is_started() -> None:
    server = TestHttpServer()

    with pytest.raises(RuntimeError, match="start it first"):
        _ = server.port


def test_it_reports_the_free_port_it_was_given() -> None:
    with TestHttpServer() as server:
        assert server.host == "127.0.0.1"
        assert server.port > 0
        assert server.base_uri == f"http://127.0.0.1:{server.port}"
        assert is_listening(server.port) is True


def test_two_servers_are_given_different_ports() -> None:
    with TestHttpServer() as first, TestHttpServer() as second:
        assert first.port != second.port


def test_it_answers_once_started() -> None:
    server = TestHttpServer()
    server.start()
    try:
        assert exchange(NOT_FOUND, port=server.port).status_code == 404
    finally:
        server.stop()


def test_a_second_start_is_a_no_op() -> None:
    server = TestHttpServer()
    server.start()
    try:
        port = server.port
        server.start()

        assert server.port == port
        assert exchange(NOT_FOUND, port=port).status_code == 404
    finally:
        server.stop()


def test_it_frees_the_port_when_stopped() -> None:
    server = TestHttpServer()
    server.start()
    server.stop()

    assert is_listening(server.port) is False


def test_a_second_stop_is_a_no_op() -> None:
    server = TestHttpServer()
    server.start()
    server.stop()

    server.stop()

    assert is_listening(server.port) is False


def test_it_can_be_started_again_after_being_stopped() -> None:
    server = TestHttpServer()
    server.start()
    server.stop()

    server.start()
    try:
        assert exchange(NOT_FOUND, port=server.port).status_code == 404
    finally:
        server.stop()


def test_it_stops_when_a_stopped_server_was_never_started() -> None:
    server = TestHttpServer()

    server.stop()

    with pytest.raises(RuntimeError, match="start it first"):
        _ = server.port


def test_it_stops_on_a_connection_that_asked_for_nothing() -> None:
    server = TestHttpServer()
    server.start()

    with socket.create_connection((HOST, server.port), timeout=5.0):
        server.stop()

    assert is_listening(server.port) is False


def test_it_runs_for_the_length_of_a_with_block() -> None:
    with TestHttpServer() as server:
        assert is_listening(server.port) is True

    assert is_listening(server.port) is False


def test_it_raises_whatever_stopped_it_from_listening() -> None:
    with TestHttpServer() as taken:
        blocked = TestHttpServer(port=taken.port)

        with pytest.raises(OSError, match="address already in use"):
            blocked.start()

    blocked.start()
    try:
        assert is_listening(blocked.port) is True
    finally:
        blocked.stop()


def test_it_listens_where_it_is_told_to() -> None:
    with TestHttpServer() as probe:
        free = probe.port

    with TestHttpServer(host="127.0.0.1", port=free) as server:
        assert server.port == free
        assert server.base_uri == f"http://127.0.0.1:{free}"
        assert is_listening(free) is True
