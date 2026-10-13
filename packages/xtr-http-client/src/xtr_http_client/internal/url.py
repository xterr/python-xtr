"""A URL read apart, fixed up, and resolved against a base.

Follows RFC 3986: section 5.2.2 for resolving a reference against a base,
section 5.2.4 for dot segments, section 2.3 for which escapes are worth
keeping.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final
from urllib.parse import quote, unquote, urlsplit

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.query import merge_query_string
from xtr_http_client.url_parts import UrlParts

if TYPE_CHECKING:
    from collections.abc import Mapping
    from urllib.parse import SplitResult

    from xtr_http_client_contracts import QueryValue

__all__ = ["parse_url", "remove_dot_segments", "resolve_url"]

ALLOWED_SCHEMES: Final = {"http": 80, "https": 443}
"""The schemes a client here speaks, with the port each implies."""

_POINTLESS_ESCAPE: Final = re.compile(
    r"(?:%(?:2[DE]|3[0-9]|[46][1-9A-F]|5F|[57][0-9A]|7E))+",
    re.IGNORECASE,
)
"""Escapes of characters that never needed escaping — the unreserved set.

Decoding them is what makes two spellings of one URL compare equal.
"""

_MUST_ESCAPE: Final = re.compile(r"[^-A-Za-z0-9._~!$&/'()\[\]*+,;=:@{}%]+")
"""Everything a path, query or fragment may not carry as itself."""

_FORBIDDEN_IN_URL: Final = ("\r", "\n", "\t")


def parse_url(
    url: str,
    query: Mapping[str, QueryValue] | None = None,
    allowed_schemes: Mapping[str, int] = ALLOWED_SCHEMES,
) -> UrlParts:
    """Read a URL apart, fixing its spelling on the way.

    The spelling is fixed so the URL sent is the one meant: escapes that never
    needed escaping are decoded, characters that cannot travel as themselves
    are encoded, the host is lowered and an international one turned into the
    ASCII form a resolver answers to, and a port the scheme already implies is
    dropped.

    What is refused is refused because it is how a URL smuggles something past
    whoever wrote it: a backslash some parsers read as a slash, a newline that
    would end the request line, a space at either end that came in with a copy
    and paste, a scheme no client here speaks.

    Args:
        url: The URL, absolute or relative.
        query: Parameters to merge into its query string, winning over what
            the URL carries.
        allowed_schemes: The schemes to accept, mapped to the port each
            implies.

    Returns:
        The five parts, each with its own punctuation.

    Raises:
        InvalidArgumentError: When the URL is malformed, or names a scheme
            that is not allowed.
    """
    _refuse_malformed(url)
    parts = _split(url)
    host, port = _authority(url, parts, allowed_schemes)
    carried = parts.query or None
    pieces = {
        "user": parts.username,
        "pass": parts.password,
        "path": parts.path,
        "query": merge_query_string(carried, query, replace=True) if query else carried,
        "fragment": parts.fragment,
    }
    fixed = {name: _fix_spelling(piece) for name, piece in pieces.items() if piece is not None}

    return UrlParts(
        scheme=f"{parts.scheme}:" if parts.scheme else None,
        authority=None if host is None else f"//{_user_info(fixed)}{host}{port}",
        path=fixed.get("path") or None,
        query=f"?{fixed['query']}" if "query" in fixed else None,
        fragment=f"#{fixed['fragment']}" if fixed.get("fragment") else None,
    )


def resolve_url(
    url: UrlParts,
    base: UrlParts | None,
    query_defaults: Mapping[str, QueryValue] | None = None,
) -> UrlParts:
    """Resolve a URL against a base one, as RFC 3986 section 5.2.2 says to.

    What the URL names, it keeps; what it leaves out, it takes from the base.
    A relative path is read as being next to the base's last segment, which is
    what makes ``orders`` under a base of ``/v1/users`` mean ``/v1/orders``
    while ``/orders`` means the root.

    Args:
        url: The URL to resolve, as :func:`parse_url` read it.
        base: The base to resolve against, or ``None`` when the URL has to
            stand on its own.
        query_defaults: Parameters to fill the query string of a relative URL
            with. They apply to a relative URL only: an absolute one was
            written for somewhere else, and a default meant for the base's
            host has no business going there.

    Raises:
        InvalidArgumentError: When the result would not be a URL anything can
            be sent to — no scheme, or no host.
    """
    if base is not None and f"{base.scheme or ''}{base.authority or ''}" == "":
        raise InvalidArgumentError(
            f'Invalid "base_uri" option: host or scheme is missing in "{base}".'
        )

    if url.scheme is None:
        if base is None or base.scheme is None:
            named = base if base is not None else url
            raise InvalidArgumentError(
                f'Invalid URL: scheme is missing in "{named}". Did you forget to add "http(s)://"?'
            )
        return _completed(_against(url, base, query_defaults), url)

    absolute = UrlParts(
        url.scheme,
        url.authority,
        remove_dot_segments(url.path or ""),
        url.query,
        url.fragment,
    )
    return _completed(absolute, url)


def remove_dot_segments(path: str) -> str:
    """Take the ``.`` and ``..`` segments out of a path.

    RFC 3986 section 5.2.4, as the loop it is written as there. The point of
    doing it before the request rather than leaving it to the server is that
    ``..`` can never climb above the root, so no path can be talked into
    naming something outside the host it was resolved against.
    """
    result = ""

    while path not in ("", ".", ".."):
        if path.startswith("../"):
            path = path[3:]
        elif path.startswith("./"):
            path = path[2:]
        elif path == "/." or path.startswith("/./"):
            path = f"/{path[3:]}"
        elif path == "/.." or path.startswith("/../"):
            climbed = result.rfind("/")
            result = result[:climbed] if climbed > 0 else ""
            path = f"/{path[4:]}"
        else:
            end = path.find("/", 1)
            end = len(path) if end == -1 else end
            result += path[:end]
            path = path[end:]

    return result


def _refuse_malformed(url: str) -> None:
    backslash = url.find("\\")
    if backslash != -1 and backslash < len(re.split(r"[?#]", url, maxsplit=1)[0]):
        raise InvalidArgumentError(f'Malformed URL "{url}": backslashes are not allowed.')
    if any(character in url for character in _FORBIDDEN_IN_URL):
        raise InvalidArgumentError(f'Malformed URL "{url}": CR/LF/TAB characters are not allowed.')
    if url != "" and (url[0] <= " " or url[-1] <= " "):
        raise InvalidArgumentError(
            f'Malformed URL "{url}": leading/trailing ASCII control characters or spaces '
            f"are not allowed."
        )


def _split(url: str) -> SplitResult:
    try:
        parts = urlsplit(url)
        _ = parts.port
    except ValueError as error:
        raise InvalidArgumentError(f'Malformed URL "{url}".') from error

    if url.startswith("//") and parts.netloc == "":
        raise InvalidArgumentError(f'Malformed URL "{url}".')

    return parts


def _authority(
    url: str,
    parts: SplitResult,
    allowed_schemes: Mapping[str, int],
) -> tuple[str | None, str]:
    port = parts.port or 0
    if parts.scheme:
        if parts.scheme not in allowed_schemes:
            allowed = '" or "'.join(allowed_schemes)
            raise InvalidArgumentError(f'Unsupported scheme in "{url}": "{allowed}" expected.')
        port = 0 if allowed_schemes[parts.scheme] == port else port

    host = parts.hostname
    if host is None:
        return None, ""

    return _ascii_host(host), f":{port}" if port else ""


def _ascii_host(host: str) -> str:
    """The host as a resolver answers to it, bracketed again when it is IPv6.

    ``urlsplit`` lowers a host and drops the brackets an IPv6 address is
    written in — the first is what comparing hosts needs, the second is what
    writing the URL back out has to undo.
    """
    if ":" in host:
        return f"[{host}]"
    if host.isascii():
        return host

    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host


def _fix_spelling(piece: str) -> str:
    if "%" in piece:
        piece = _POINTLESS_ESCAPE.sub(lambda match: unquote(match.group(0)), piece)
    return _MUST_ESCAPE.sub(lambda match: quote(match.group(0), safe=""), piece)


def _user_info(fixed: Mapping[str, str]) -> str:
    if "user" not in fixed:
        return ""
    password = f":{fixed['pass']}" if "pass" in fixed else ""
    return f"{fixed['user']}{password}@"


def _against(
    url: UrlParts,
    base: UrlParts,
    query_defaults: Mapping[str, QueryValue] | None,
) -> UrlParts:
    if url.authority is not None:
        path = remove_dot_segments(url.path or "")
        return UrlParts(base.scheme, url.authority, path, url.query, url.fragment)

    path, query = _rebased(url.path, url.query, base)
    if query_defaults:
        merged = merge_query_string((query or "")[1:], query_defaults, replace=False)
        query = f"?{merged or ''}"

    return UrlParts(base.scheme, base.authority, path, query, url.fragment)


def _rebased(path: str | None, query: str | None, base: UrlParts) -> tuple[str | None, str | None]:
    if path is None:
        return base.path, query if query is not None else base.query

    if not path.startswith("/"):
        if base.path is None:
            path = f"/{path}"
        else:
            segments = base.path.split("/")
            segments[-1:] = [path]
            path = "/".join(segments)

    return remove_dot_segments(path), query


def _completed(resolved: UrlParts, given: UrlParts) -> UrlParts:
    scheme, authority, path, query, fragment = resolved
    if scheme is not None and authority is None:
        raise InvalidArgumentError(f'Invalid URL: host is missing in "{given}".')

    return UrlParts(scheme, authority, path or "/", None if query == "?" else query, fragment)
