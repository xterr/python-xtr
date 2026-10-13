"""The response a client hands back, and what a caller reads off it."""

from __future__ import annotations

from .http_response import HttpResponse
from .httpx_response import to_http_response
from .json_mock_response import JsonMockResponse
from .mock_response import MockResponse

__all__ = ["HttpResponse", "JsonMockResponse", "MockResponse", "to_http_response"]
