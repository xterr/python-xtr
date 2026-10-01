"""The firewall configuration for the self-issued-token authenticator."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["JwtAuthenticatorConfig"]


@dataclass(frozen=True, slots=True)
class JwtAuthenticatorConfig:
    """A firewall's ``jwt`` authenticator, mirroring the reference ``jwt: ~`` node.

    A firewall accepts self-issued tokens by listing one of these under its
    authenticators; there is nothing more to set — the keys, the algorithm and
    the extractors all come from the bundle's own configuration. The optional
    ``provider`` overrides the firewall's user provider, and ``authenticator``
    names a registered authenticator service to build instead of the default.

    Attributes:
        provider: The user provider to load the token's user through, or ``None``
            to use the firewall's own.
        authenticator: A registered authenticator service to use instead of the
            one this bundle builds, or ``None`` for the default.
    """

    provider: str | None = None
    authenticator: type | None = None
