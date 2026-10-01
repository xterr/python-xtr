"""A firewall whose authenticator config has no factory to build it."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_dependency_injection import configure

from xtr_security.bundle import FirewallConfig, SecurityConfig

__all__ = ["UnknownAuthenticatorConfig", "security"]


@dataclass(frozen=True, slots=True)
class UnknownAuthenticatorConfig:
    """An authenticator configuration no registered factory answers to."""


@configure
def security() -> SecurityConfig:
    """Return a configuration a build cannot wire: no factory for the authenticator."""
    return SecurityConfig(
        firewalls={
            "api": FirewallConfig(pattern=r"^/api", authenticators=(UnknownAuthenticatorConfig(),))
        },
    )
