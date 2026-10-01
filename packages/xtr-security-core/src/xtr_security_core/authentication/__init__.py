"""Authentication: tokens, where they are kept, and how strongly they are trusted."""

from __future__ import annotations

from .authentication_trust_resolver import AuthenticationTrustResolver
from .authentication_trust_resolver_interface import AuthenticationTrustResolverInterface

__all__ = [
    "AuthenticationTrustResolver",
    "AuthenticationTrustResolverInterface",
]
