"""Reading the settings a firewall's access-token authenticator carries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security.bundle.authenticator_configs import AccessTokenConfig

if TYPE_CHECKING:
    from xtr_security.firewall_config import FirewallConfig

__all__ = ["access_token_settings_of", "realm_of"]


def realm_of(firewall: FirewallConfig) -> str | None:
    """Read the realm off the firewall's first access-token authenticator, if any."""
    settings = access_token_settings_of(firewall)
    return settings.realm if settings is not None else None


def access_token_settings_of(firewall: FirewallConfig) -> AccessTokenConfig | None:
    """Return the firewall's first access-token authenticator configuration, if any.

    The scope-denied handler reads its RFC 9728 ``resource_metadata`` URI and
    its sender constraint off the same authenticator the challenge answers
    for, so the two stay one configuration.
    """
    for authenticator in firewall.authenticators:
        if isinstance(authenticator, AccessTokenConfig):
            return authenticator
    return None
