"""An impersonation address could not be generated."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

__all__ = ["ImpersonationError"]


class ImpersonationError(SecurityError, RuntimeError):
    """A generated impersonation address was asked for and could not be built.

    Also a :class:`RuntimeError`. The causes are configuration gaps: no
    firewall with a user switch for the request, a switch that asks for a
    cross-site request forgery token while no manager was given to mint
    one, or a dedicated path configured as a route name, which no routing
    component here can resolve.
    """
