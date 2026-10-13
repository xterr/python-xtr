"""The response a client hands back, and what a caller reads off it."""

from __future__ import annotations

from .http_response import HttpResponse
from .httpx_response import to_http_response

__all__ = ["HttpResponse", "to_http_response"]
