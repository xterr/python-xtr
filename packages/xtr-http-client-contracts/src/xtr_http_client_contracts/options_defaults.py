"""What a request asks for when nobody asked for anything in particular."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from .request_options import RequestOptions

__all__ = ["OPTIONS_DEFAULTS"]

OPTIONS_DEFAULTS: Final[RequestOptions] = {
    # No credentials are sent unless the caller asks for them.
    "auth_basic": None,
    "auth_bearer": None,
    # Nothing is added to the URL, nothing is sent alongside it.
    "query": {},
    "headers": {},
    "body": b"",
    "json": None,
    # Carried for the caller, never read.
    "user_data": None,
    # Enough hops for any sane chain, few enough to end a loop.
    "max_redirects": 20,
    # The best version the connection offers.
    "http_version": None,
    # Every URL is absolute until a caller says otherwise.
    "base_uri": None,
    # 60 seconds: long enough for a slow server, short enough to free the
    # connection.
    "timeout": None,
    # Neither the transfer as a whole nor connecting is time limited: the
    # idle timeout already ends a transfer nothing is coming in on.
    "max_duration": 0.0,
    "max_connect_duration": 0.0,
    # Hosts are resolved the usual way, and reached without a proxy.
    "resolve": {},
    "proxy": None,
    "no_proxy": None,
    # A certificate is checked, and checked against the host asked for.
    # Turning either off is a decision an application makes in the open.
    "verify_peer": True,
    "verify_host": True,
    # The trust store and the client certificate are whatever the platform
    # offers.
    "cafile": None,
    "capath": None,
    "local_cert": None,
    "local_pk": None,
    "passphrase": None,
    # How often a client that retries tries again.
    "max_retries": 3,
    # Additional options a client may ignore when it does not support them,
    # unlike the regular options it must refuse; `use_persistent_connections`
    # says whether to use persistent connections where supported.
    "extra": {"use_persistent_connections": False},
}
"""Every option the contract names, mapped to what it means to leave it out.

A client merges what a request was given over its own defaults, and those
over this, so every option always has a value by the time a request is made.
Nothing here is an instruction — it is the absence of one, which is why the
defaults name no host, no credentials and no deadline.

The entries worth reading twice: ``timeout`` of ``None`` is not "no timeout"
but 60 seconds; ``max_duration`` and ``max_connect_duration`` of zero *are*
"no limit".

The mapping is shared, so merge into a copy rather than writing to it.
"""
