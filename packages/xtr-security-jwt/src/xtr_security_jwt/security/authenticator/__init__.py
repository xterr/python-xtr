"""The authenticator that proves a caller by a self-issued token."""

from __future__ import annotations

from .jwt_authenticator import JwtAuthenticator

__all__ = ["JwtAuthenticator"]
