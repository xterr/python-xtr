"""An async HTTP client: typed options in, a response read on demand out.

One interface with clients behind it — one that opens real connections and
streams what comes back, and :class:`HttpClient`, the one call that hands one
over so nothing else has to name it.

A request returns once the status line and headers have arrived, whatever the
status; the body is read when the caller asks for it, as a whole or piece by
piece.
"""

from __future__ import annotations

from .http_client import HttpClient
from .http_client_mixin import HttpClientMixin
from .httpx_http_client import HttpxHttpClient
from .response import HttpResponse

__all__ = ["HttpClient", "HttpClientMixin", "HttpResponse", "HttpxHttpClient"]
