"""The token answer a sign-in is handed.

A sign-in ends at the token endpoint like any authorization code flow, and its
answer is the bearer answer with one field more: the ID token stating who
signed in. :class:`IdTokenResponse` is that answer.
"""

from __future__ import annotations

from .id_token_response import IdTokenResponse

__all__ = ["IdTokenResponse"]
