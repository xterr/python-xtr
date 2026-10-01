"""The errors the xtr-security bundle raises.

The family's one root is :class:`~xtr_security_core.exception.SecurityError`;
the bundle adds :class:`InvalidConfigurationError` for a configuration it cannot
turn into services, so ``except SecurityError`` still catches everything.
"""

from __future__ import annotations

from .invalid_configuration_error import InvalidConfigurationError

__all__ = ["InvalidConfigurationError"]
