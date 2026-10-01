"""A firewall was asked for by a name that is not configured."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core.exception import SecurityError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["UnknownFirewallError"]


class UnknownFirewallError(SecurityError, LookupError):
    """No firewall is configured under the name asked for.

    Also a :class:`LookupError`. Names the firewalls that are configured, so
    the mistake — a typo, a firewall never declared — is plain from the error.

    Attributes:
        name: The name that matched no firewall.
        configured: The names that are configured.
    """

    name: str
    configured: tuple[str, ...]

    def __init__(self, name: str, configured: Sequence[str] = ()) -> None:
        """Record the unknown name and the names that are configured."""
        self.name = name
        self.configured = tuple(configured)
        known = ", ".join(f'"{one}"' for one in self.configured) or "none"
        super().__init__(f'The firewall "{name}" is not configured. Configured: {known}.')
