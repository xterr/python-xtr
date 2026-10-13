from __future__ import annotations

from xtr_http_client import UrlParts


def test_the_parts_read_back_as_the_url_they_came_from() -> None:
    parts = UrlParts("http:", "//example.com", "/orders", "?page=2", "#top")

    assert str(parts) == "http://example.com/orders?page=2#top"


def test_a_part_nobody_named_contributes_nothing() -> None:
    assert str(UrlParts(None, None, "/orders", None, None)) == "/orders"
    assert str(UrlParts(None, None, None, None, None)) == ""


def test_the_parts_are_named_so_a_client_can_read_one_of_them() -> None:
    parts = UrlParts("https:", "//example.com:8443", "/", None, None)

    assert parts.scheme == "https:"
    assert parts.authority == "//example.com:8443"
    assert parts.path == "/"
    assert parts.query is None
    assert parts.fragment is None
    assert tuple(parts) == ("https:", "//example.com:8443", "/", None, None)
