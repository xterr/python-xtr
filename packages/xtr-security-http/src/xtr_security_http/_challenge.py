r"""Writing a ``WWW-Authenticate`` challenge: quoting and cache headers.

A challenge's ``realm``, ``error_description`` and ``scope`` are written as
RFC 7235 ``quoted-string`` values; a ``\`` or a ``"`` inside one must be
backslash-escaped or the header is malformed. Both the access-token
authenticator's challenge and the insufficient-scope handler's challenge quote
their values through here, so the escaping is written once.

Every challenge response also carries the no-store cache directives
:func:`no_store_headers` adds, so a ``401`` or ``403`` is never kept by a shared
cache or a browser and replayed.
"""

from __future__ import annotations

import re
from typing import Final

from xtr_security_core.exception import InvalidArgumentError

__all__ = ["no_store_headers", "quote_auth_param"]

#: The control characters a ``quoted-string`` cannot carry. Its ``qdtext``
#: admits HTAB and SP; every other character below ``%x20``, and ``%x7f``, has
#: no spelling in the grammar — not even as a ``quoted-pair``.
_REFUSED_CONTROLS: Final = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")

#: The cache directives a challenge response carries, so neither a shared cache
#: nor a browser keeps a ``401``/``403`` and replays it to another caller or
#: after the credential changed. ``no-store`` is the HTTP/1.1 directive;
#: ``Pragma: no-cache`` is the HTTP/1.0 belt-and-braces an old intermediary
#: still reads.
_NO_STORE: Final = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def quote_auth_param(value: str) -> str:
    r"""Return ``value`` as an RFC 7235 ``quoted-string``, escaping ``\`` and ``"``.

    Raises:
        InvalidArgumentError: When ``value`` carries a control character. A
            ``quoted-string`` has no way to write one, so the challenge would be
            malformed — and a CR or an LF would split the header. Every value
            quoted here is declared by the application, so this is a mistake to
            report where it is made, not a request to answer.
    """
    refused = _REFUSED_CONTROLS.search(value)
    if refused is not None:
        raise InvalidArgumentError(
            f"An auth-param value cannot carry the control character {refused.group()!r}.",
        )
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def no_store_headers(**headers: str) -> dict[str, str]:
    """Return ``headers`` with the no-store cache directives a challenge needs.

    A challenge response must not be cached: a shared cache that kept a ``401``
    would answer another caller's request with it, and a browser that kept one
    would replay it after the credential changed. Every challenge this package
    writes merges its own headers — a ``WWW-Authenticate`` — through here so the
    directives are set in one place.
    """
    return {**_NO_STORE, **headers}
