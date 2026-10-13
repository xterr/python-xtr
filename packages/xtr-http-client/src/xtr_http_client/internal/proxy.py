"""The proxy a request goes through, from the option or the environment."""

from __future__ import annotations

import os
import re
from base64 import b64encode
from typing import TYPE_CHECKING, Final
from urllib.parse import unquote, urlsplit

from xtr_http_client_contracts import TransportError

from xtr_http_client.proxy_config import ProxyConfig

if TYPE_CHECKING:
    from xtr_http_client.url_parts import UrlParts

__all__ = ["get_proxy"]

_TRANSPORTS: Final = {"http": ("tcp", 80), "https": ("ssl", 443)}
_SEPARATORS: Final = re.compile(r"[\s,]+")


def get_proxy(proxy: str | None, url: UrlParts, no_proxy: str | None) -> ProxyConfig | None:
    """Work out what a request should go through, if anything.

    The option wins. With no option the environment decides, the way every
    other HTTP tool on a machine reads it, so a process behind a proxy needs
    no configuration of its own: ``https_proxy`` for a secure request,
    ``http_proxy`` or ``all_proxy`` otherwise, and ``no_proxy`` for the hosts
    to reach directly.

    ``HTTP_PROXY`` in uppercase is deliberately not read. It is a request
    header away from being an environment variable under CGI, so anyone who
    can send a header could choose where this process connects.

    Args:
        proxy: The proxy the caller asked for, or ``None`` to let the
            environment answer.
        url: The URL being requested, whose scheme decides which variable
            applies.
        no_proxy: The hosts to reach directly, or ``None`` to read them from
            the environment.

    Returns:
        What to connect through, or ``None`` to go direct.

    Raises:
        TransportError: When the proxy names no host, or asks for a transport
            that is not HTTP.
    """
    named = _named(proxy, url)
    if named is None:
        return None

    parts = urlsplit(named if "//" in named else f"//{named}")
    scheme = parts.scheme or "http"
    if parts.hostname is None:
        raise TransportError("Invalid HTTP proxy: host is missing.")
    if scheme not in _TRANSPORTS:
        raise TransportError(f'Unsupported proxy scheme "{scheme}": "http" or "https" expected.')

    transport, default_port = _TRANSPORTS[scheme]
    listed = no_proxy if no_proxy is not None else _first_set("no_proxy", "NO_PROXY")

    return ProxyConfig(
        url=f"{transport}://{parts.hostname}:{parts.port or default_port}",
        auth=_authorization(parts.username, parts.password),
        no_proxy=tuple(_SEPARATORS.split(listed)) if listed else (),
    )


def _named(proxy: str | None, url: UrlParts) -> str | None:
    if proxy is not None:
        return proxy

    named = _first_set("http_proxy", "all_proxy", "ALL_PROXY")
    if url.scheme == "https:":
        return _first_set("https_proxy", "HTTPS_PROXY") or named

    return named


def _first_set(*names: str) -> str | None:
    """The first of these variables that is set to anything."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value

    return None


def _authorization(user: str | None, password: str | None) -> str | None:
    if user is None:
        return None

    credentials = f"{unquote(user)}:{unquote(password or '')}".encode()
    return f"Basic {b64encode(credentials).decode()}"
