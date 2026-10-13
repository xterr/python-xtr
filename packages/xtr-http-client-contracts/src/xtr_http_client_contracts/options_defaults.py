"""What a request asks for when nobody asked for anything in particular."""

from __future__ import annotations

import ssl
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
    # The body is kept, so reading it twice works; a transfer too large to
    # hold is what `buffer=False` is for.
    "buffer": True,
    "on_progress": None,
    # Hosts are resolved the usual way.
    "resolve": {},
    # `None` rather than "no proxy": the proxy environment variables still
    # apply, and that is what an application expects of a command it runs
    # behind one.
    "proxy": None,
    "no_proxy": None,
    # The client decides how long a transfer may go quiet for; the clients
    # here settle on 60 seconds, which is long enough for a slow server and
    # short enough to free the connection.
    "timeout": None,
    # Neither the transfer as a whole nor connecting is time limited: the
    # idle timeout already ends a transfer nothing is coming in on.
    "max_duration": 0.0,
    "max_connect_duration": 0.0,
    # Any local interface.
    "bindto": "0",
    # A certificate is checked, and checked against the host asked for.
    # Turning either off is a decision an application makes in the open.
    "verify_peer": True,
    "verify_host": True,
    # The trust store, the cipher suites and the client certificate are
    # whatever the platform offers.
    "cafile": None,
    "capath": None,
    "local_cert": None,
    "local_pk": None,
    "passphrase": None,
    "ciphers": None,
    "peer_fingerprint": None,
    "capture_peer_cert_chain": False,
    # Everything below TLS 1.2 is refused.
    "crypto_method": ssl.TLSVersion.TLSv1_2,
    # The contract names no extra of its own; each client documents what it
    # reads here.
    "extra": {},
}
"""Every option the contract names, mapped to what it means to leave it out.

A client merges what a request was given over its own defaults, and those
over this, so every option always has a value by the time a request is made.
Nothing here is an instruction — it is the absence of one, which is why the
defaults name no host, no credentials and no deadline.

The entries worth reading twice: ``timeout`` of ``None`` is not "no timeout"
but "the client's own", 60 seconds in the clients here; ``max_duration`` and
``max_connect_duration`` of zero *are* "no limit"; ``bindto`` of ``"0"`` is
any local interface; and ``crypto_method`` is a floor, not a choice of
version.

The mapping is shared, so merge into a copy rather than writing to it.
"""
