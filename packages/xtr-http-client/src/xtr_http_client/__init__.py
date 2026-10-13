"""An async HTTP client: typed options in, a response read on demand out.

One interface with clients behind it — one that opens real connections and
streams what comes back, one that answers from a script a test wrote, three
that wrap another and add what every application writes again (a set of
defaults per service, a refusal to reach inwards, and a request made again
while that is worth doing), and :class:`HttpClient`, the one call that hands
one over so nothing else has to name it.

A request returns once the status line and headers have arrived, whatever the
status; the body is read when the caller asks for it, as a whole or piece by
piece.
"""

from __future__ import annotations

from .http_client import HttpClient
from .http_client_mixin import HttpClientMixin
from .httpx_http_client import HttpxHttpClient
from .mock_http_client import MockHttpClient
from .no_private_network_http_client import NoPrivateNetworkHttpClient
from .response import HttpResponse, JsonMockResponse, MockResponse
from .retry import GenericRetryStrategy, RetryContext, RetryStrategyInterface
from .retryable_http_client import RetryableHttpClient
from .scoping_http_client import ScopingHttpClient

__all__ = [
    "GenericRetryStrategy",
    "HttpClient",
    "HttpClientMixin",
    "HttpResponse",
    "HttpxHttpClient",
    "JsonMockResponse",
    "MockHttpClient",
    "MockResponse",
    "NoPrivateNetworkHttpClient",
    "RetryContext",
    "RetryStrategyInterface",
    "RetryableHttpClient",
    "ScopingHttpClient",
]
