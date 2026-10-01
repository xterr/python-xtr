"""Something a booted kernel provides was read before boot, or outside a request."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

__all__ = ["FirewallNotBootedError"]


class FirewallNotBootedError(SecurityError, RuntimeError):
    """A firewall's booted state was read too early, or outside a request.

    The OpenAPI scheme a firewall contributes is resolved from the booted
    kernel serving the current request. Read it before the kernel has booted,
    or with no request in scope, and there is nothing to resolve — this is
    raised rather than a wrong, silently-chosen answer. Also a
    :class:`RuntimeError`.
    """
