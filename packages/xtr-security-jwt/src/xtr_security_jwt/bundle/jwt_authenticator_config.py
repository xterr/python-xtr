"""The firewall configuration for the self-issued-token authenticator."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["JwtAuthenticatorConfig"]


@dataclass(frozen=True, slots=True)
class JwtAuthenticatorConfig:
    """A firewall's ``jwt`` authenticator.

    A firewall accepts self-issued tokens by listing one of these under its
    authenticators; there is nothing to set — the keys, the algorithm and the
    extractors all come from the bundle's own configuration, and the user is
    loaded through the firewall's own provider.
    """
