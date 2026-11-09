r"""Telling whether a redirect target the client named leads back to the request's origin.

A login, a failed login and a user switch can each be told where to send the
caller next: a field of the submitted form, a parameter of the query string,
the page the caller came from. The client wrote that target — and so did
whoever wrote the link or the page the client followed — so a target on
another site, honoured as it is, sends a caller who has just signed in off to
it. A target the client named is honoured only when it leads back to the
origin the request reached: a path of the application's own, or an absolute
URL carrying the request's scheme, host and port.

The target is weighed the way a browser reads it, not only the way a URL
parser does. A browser reads a ``\`` in an ``http(s)`` address as a ``/``, and
skips a tab or a line break wherever one stands, so ``/\host`` leads to
``//host`` — another site — and where a parser and a browser split an
authority at different places, they name different hosts. A target carrying a
backslash or a control character is refused outright.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["is_same_origin"]

#: What a browser does not read as it is written: a backslash, read as a slash
#: in an ``http(s)`` address, and the control characters — the tab and the line
#: breaks among them, which it skips wherever they stand.
_AMBIGUOUS: Final = re.compile(r"[\\\x00-\x1f\x7f]")

#: The schemes a redirect target may name, each with the port it answers on
#: when the address writes none.
_DEFAULT_PORTS: Final[dict[str, int]] = {"http": 80, "https": 443}


def is_same_origin(request: ServerRequestInterface, target: str) -> bool:
    """Tell whether ``target`` leads back to the origin ``request`` reached.

    A path qualifies when it opens with a single ``/``: a second one makes it
    the address of another host, reached over the request's scheme. An
    absolute URL qualifies when it names ``http`` or ``https`` and the
    request's own scheme, host and port — a port it leaves out read as its
    scheme's. A relative reference never qualifies, nor does a target
    carrying a backslash or a control character.
    """
    if _AMBIGUOUS.search(target) is not None:
        return False
    if target.startswith("/"):
        return not target.startswith("//")
    origin = _origin_of(target)
    return origin is not None and origin == _origin_of(str(request.get_uri()))


def _origin_of(url: str) -> tuple[str, str, int] | None:
    """Return the scheme, host and port ``url`` leads to, or ``None`` for no web origin.

    Both sides of the comparison are read here, through the one parser, so a
    host is compared with a host written the same way — an IP literal without
    its brackets on either side.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        # A port that is no number, or brackets holding no address: an
        # authority no origin can be told from.
        return None
    default_port = _DEFAULT_PORTS.get(parts.scheme)
    if default_port is None or parts.hostname is None:
        return None
    return parts.scheme, parts.hostname, default_port if port is None else port
