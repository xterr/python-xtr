"""Building a Starlette request for the security-bundle tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.requests import Request

if TYPE_CHECKING:
    from collections.abc import Mapping


def make_request(
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    query: str = "",
    body: bytes = b"",
) -> Request:
    """Return a request with the given method, headers, query string and body."""
    header_pairs = [
        (name.lower().encode(), value.encode()) for name, value in (headers or {}).items()
    ]

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": method,
            "headers": header_pairs,
            "query_string": query.encode(),
        },
        receive,
    )
