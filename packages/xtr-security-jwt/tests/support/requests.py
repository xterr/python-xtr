"""A tiny helper building a Starlette request out of headers, cookies and a query."""

from __future__ import annotations

from urllib.parse import urlencode

from starlette.requests import Request

__all__ = ["make_request"]


def make_request(
    *,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
) -> Request:
    """Build a GET request carrying the given headers, cookies and query."""
    raw_headers: list[tuple[bytes, bytes]] = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    if cookies:
        cookie = "; ".join(f"{name}={value}" for name, value in cookies.items())
        raw_headers.append((b"cookie", cookie.encode("latin-1")))
    query_string = urlencode(query or {}).encode("latin-1")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": raw_headers,
        "query_string": query_string,
    }
    return Request(scope)
