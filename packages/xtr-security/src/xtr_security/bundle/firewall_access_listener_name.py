"""The name a firewall's access listener is registered under."""

from __future__ import annotations

__all__ = ["firewall_access_listener_name"]


def firewall_access_listener_name(firewall: str) -> str:
    """Return the name of the listener deciding ``firewall``'s access rules.

    The qualifier it is aliased under, as
    :class:`~xtr_security_http.firewall.firewall_listener_interface.FirewallListenerInterface`,
    and what a ``@FirewallListenerOrder`` constraint names to order a listener
    against the firewall's own access step::

        @FirewallListenerOrder(before="security.access_listener.api")
        class AuditListener(AbstractListener): ...
    """
    return f"security.access_listener.{firewall}"
