"""What an HTTP exchange is logged as, with nothing in it that could be a credential.

The log ends up wherever a sent message or an error goes, so it keeps what tells an exchange
apart and leaves out what may carry a secret: the request line without the URL's user info and
query — either may hold a key — then each status and header line of the answer, the value of a
cookie or authorization header redacted. The request's own headers, the ``Authorization`` a
provider is called with among them, are never known to it. An answer's line is the provider's
to write: a control character in it is shown escaped, and a long one is cut short.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast
from urllib.parse import urlsplit

__all__ = ["http_debug"]

_REDACTED: Final = frozenset({"authorization", "cookie", "proxy-authorization", "set-cookie"})
_LINE_LENGTH: Final = 1000


def http_debug(info: object) -> str:
    """Log the exchange ``info`` describes — what a response's ``get_info()`` returns."""
    if not isinstance(info, Mapping):
        return ""
    known = cast("Mapping[object, object]", info)
    method, url = known.get("http_method"), known.get("url")
    request = (
        f"> {method} {_url(url)}\n" if isinstance(method, str) and isinstance(url, str) else ""
    )
    return request + "".join(f"< {_line(line)}\n" for line in _lines(known.get("response_headers")))


def _url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return "[unreadable URL]"
    return f"{parts.scheme}://{parts.netloc.rpartition('@')[2]}{parts.path}"


def _lines(lines: object) -> list[str]:
    if not isinstance(lines, list):
        return []
    return [line for line in cast("list[object]", lines) if isinstance(line, str)]


def _line(line: str) -> str:
    name, colon, _ = line.partition(":")
    if colon and name.strip().lower() in _REDACTED:
        return f"{name}: [redacted]"
    shown = "".join(char if char.isprintable() else repr(char)[1:-1] for char in line)
    return shown[:_LINE_LENGTH] + ("…" if len(shown) > _LINE_LENGTH else "")
