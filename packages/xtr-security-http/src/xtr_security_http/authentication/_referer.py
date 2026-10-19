"""The ``Referer`` header weighed as a redirect target.

A login that answers with a redirect may be asked to send the caller back
where they came from instead — the page that linked to the login, named by
the ``Referer`` header. The header is the browser's own word, so it is
weighed before it is trusted: the query string is dropped (it is not a
place), the host is checked where a save demands one, and the two pages
that must never win — the login page itself and the page the request
asked for — are recognised and set aside.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["names_login_or_current", "names_request_host", "referer_of"]


def referer_of(request: ServerRequestInterface) -> str | None:
    """Return the request's ``Referer`` without its query string, or ``None``.

    The query string is not a place to return to — it is what the page that
    linked here was asked — so it is dropped before the header is weighed at
    all.
    """
    header = request.get_header_line("Referer")
    if header == "":
        return None
    return header.split("?", 1)[0]


def names_request_host(request: ServerRequestInterface, referer: str) -> bool:
    """Tell whether ``referer`` names a page on the host ``request`` arrived at.

    Only the host is weighed, not the scheme: a page on the same host over
    either scheme is a page of the same application, and the port is spelled
    out only when the request's URI carries one.
    """
    parsed = urlsplit(referer)
    if parsed.scheme not in ("http", "https"):
        return False
    uri = request.get_uri()
    host = uri.get_host()
    port = uri.get_port()
    if port is None:
        return parsed.netloc == host
    return parsed.netloc in {host, f"{host}:{port}"}


def names_login_or_current(request: ServerRequestInterface, referer: str, login_path: str) -> bool:
    """Tell whether ``referer`` names the login page or the page the request asked for.

    Both are weighed by path: the login page is wherever its configured path
    places it — a path or an absolute URL, the path is the part that names
    the page — and the page the request asked for is the request's own path,
    read as it travels. A referer naming either is no place to return to:
    the first is where the caller already is, the second is what sent them
    to the login.
    """
    path = urlsplit(referer).path
    if path == unquote(request.get_uri().get_path()):
        return True
    return path == urlsplit(login_path).path
