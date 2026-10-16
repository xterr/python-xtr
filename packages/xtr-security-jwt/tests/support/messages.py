"""A tiny helper building a request message out of headers, cookies and a query."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from xtr_http_message import ServerRequest

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["make_message"]


def make_message(
    *,
    headers: Mapping[str, str] | None = None,
    cookies: Mapping[str, str] | None = None,
    query: Mapping[str, str] | None = None,
) -> ServerRequest:
    """Build a GET request message carrying the given headers, cookies and query."""
    asked = f"?{urlencode(query)}" if query else ""
    message = ServerRequest("GET", f"https://example.com/{asked}", dict(headers or {}))
    if cookies:
        message = message.with_cookie_params(dict(cookies))
    return message
