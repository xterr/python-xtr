"""The responses this package hands back, and the run of chunks they arrive in."""

from __future__ import annotations

from .http_client_response import HttpClientResponse
from .response_stream import ResponseStream

__all__ = ["HttpClientResponse", "ResponseStream"]
