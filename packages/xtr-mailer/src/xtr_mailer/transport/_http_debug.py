"""What an HTTP exchange is logged as, with nothing in it that could be a credential.

The log ends up wherever a sent message or an error goes, so it keeps what tells an exchange
apart and leaves out what may carry a secret. The request line is written without the URL's
user info and query — either may hold a key. Then come the status and header lines of the
answer, every redirect hop included, as the provider wrote them but for what it may echo back:
the value of a header named after a credential — an authorization, an authentication challenge,
a cookie, a session, a token, a secret or a key — is redacted, and every URL a value carries,
whole or within, loses its user info, query and fragment as the request's does. The request's
own headers, the ``Authorization`` a provider is called with among them, are never known to it.

A line is the provider's to write: a control character in it — in its name as in its value —
is shown escaped, so no line of the log ever spans two; a long line is cut short, and only the
first lines of a long answer are kept.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final, cast
from urllib.parse import urlsplit

__all__ = ["http_debug"]

_REDACTED_NAMES: Final = frozenset(
    {
        "authentication-info",
        "authorization",
        "cookie",
        "proxy-authenticate",
        "proxy-authentication-info",
        "proxy-authorization",
        "set-cookie",
        "set-cookie2",
        "www-authenticate",
        "x-api-key",
    }
)
_REDACTED_WORDS: Final = ("auth", "cookie", "key", "secret", "session", "token")
# The headers whose whole value is a URI reference, relative ones included.
_URI_VALUED: Final = frozenset({"content-location", "location"})
_ABSOLUTE_URL: Final = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^\s<>\"']*")
_BRACKETED: Final = re.compile(r"<([^<>]*)>")
_URL_PARAMETER: Final = re.compile(r"(\burl\s*=\s*)([^\s\"']*)", re.IGNORECASE)
_LINE_LENGTH: Final = 1000
_LINE_COUNT: Final = 100


def http_debug(info: object) -> str:
    """Log the exchange ``info`` describes — what a response's ``get_info()`` returns."""
    if not isinstance(info, Mapping):
        return ""
    known = cast("Mapping[object, object]", info)
    method, url = known.get("http_method"), known.get("url")
    request = (
        f"> {method} {_reference(url)}\n"
        if isinstance(method, str) and isinstance(url, str)
        else ""
    )
    lines = _lines(known.get("response_headers"))
    answer = "".join(f"< {_line(line)}\n" for line in lines[:_LINE_COUNT])
    if len(lines) > _LINE_COUNT:
        answer += f"< … {len(lines) - _LINE_COUNT} more lines\n"
    return request + answer


def _reference(url: str) -> str:
    """Write ``url`` — absolute or relative — without its user info, query and fragment."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "[unreadable URL]"
    scheme = f"{parts.scheme}:" if parts.scheme else ""
    authority = f"//{parts.netloc.rpartition('@')[2]}" if parts.netloc else ""
    return f"{scheme}{authority}{parts.path}"


def _lines(lines: object) -> list[str]:
    if not isinstance(lines, list):
        return []
    return [line for line in cast("list[object]", lines) if isinstance(line, str)]


def _line(line: str) -> str:
    name, colon, value = line.partition(":")
    shown = f"{name}:{_value(name.strip().lower(), value)}" if colon else line
    escaped = "".join(char if char.isprintable() else repr(char)[1:-1] for char in shown)
    return escaped[:_LINE_LENGTH] + ("…" if len(escaped) > _LINE_LENGTH else "")


def _value(name: str, value: str) -> str:
    if name in _REDACTED_NAMES or any(word in name for word in _REDACTED_WORDS):
        return " [redacted]"
    if name in _URI_VALUED:
        return f" {_reference(value.strip())}"
    value = _BRACKETED.sub(lambda found: f"<{_reference(found[1])}>", value)
    value = _URL_PARAMETER.sub(lambda found: found[1] + _reference(found[2]), value)
    return _ABSOLUTE_URL.sub(lambda found: _reference(found[0]), value)
