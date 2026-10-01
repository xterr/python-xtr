"""The OIDC key material a firewall's access-token authenticator verifies with."""

from __future__ import annotations

from .oidc_jwks import OidcKeySetProviderInterface, StaticOidcKeySetProvider

__all__ = ["OidcKeySetProviderInterface", "StaticOidcKeySetProvider"]
