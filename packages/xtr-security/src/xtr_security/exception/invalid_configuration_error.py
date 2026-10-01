"""The error the security bundle raises for a configuration it cannot build."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

__all__ = ["InvalidConfigurationError"]


class InvalidConfigurationError(SecurityError, ValueError):
    """A security configuration value the bundle cannot turn into services.

    Derives from :class:`~xtr_security_core.exception.SecurityError` so one
    ``except SecurityError`` still catches everything the family raises, and
    from :class:`ValueError` because a bad configuration is a bad argument. It
    is raised as the configuration is validated — an unknown provider named by a
    firewall, a firewall that is not stateless, two authenticators of one key —
    and as the container is built, when a configured authenticator or token
    handler has no factory to build it, or an entry point cannot be resolved.
    """
