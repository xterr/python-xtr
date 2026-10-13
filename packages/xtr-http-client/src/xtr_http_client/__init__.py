"""An async HTTP client: typed options in, a response read on demand out.

One interface with several clients behind it — a backend that opens the connections and
streams what comes back, a scoping client that applies a set of defaults per URL, a guard that
refuses addresses only this process can reach, and a mock client that answers from a script
instead of the network.

A request returns once the status line and headers have arrived, whatever the status; the body
is read when the caller asks for it, as a whole or chunk by chunk.
"""

from __future__ import annotations

from .http_client_mixin import HttpClientMixin

__all__ = ["HttpClientMixin"]
