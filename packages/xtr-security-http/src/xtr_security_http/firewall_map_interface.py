"""What resolves a request's firewall: by name, or by matching the request.

The firewall runner asks this for the firewall to run — the one bound by name,
or the first whose matcher claims the request — and the OpenAPI scheme registry
and ``debug:firewall`` read the firewalls it holds. The concrete map that pairs
each firewall with its matcher is built by the bundle; the runtime here depends
only on this shape, so a firewall runs without knowing how the map was built.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request

    from xtr_security_http.firewall_context_interface import FirewallContextInterface

__all__ = ["FirewallMapInterface"]


@runtime_checkable
class FirewallMapInterface(Protocol):
    """Holds an application's firewalls, found by name or by matching a request.

    A firewall bound by name is looked up directly; an unbound one is matched to
    the first firewall whose matcher claims the request, in registration order.
    """

    def has(self, name: str) -> bool:
        """Tell whether a firewall is registered under ``name``."""
        ...

    def get(self, name: str) -> FirewallContextInterface:
        """Return the firewall named ``name``.

        Raises:
            UnknownFirewallError: When no firewall carries that name.
        """
        ...

    def match(self, request: Request) -> FirewallContextInterface | None:
        """Return the first firewall whose matcher claims ``request``, or ``None``."""
        ...

    def names(self) -> tuple[str, ...]:
        """Return the names of every firewall registered."""
        ...
