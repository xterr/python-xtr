"""The name a firewall's manager listener is registered under."""

from __future__ import annotations

__all__ = ["firewall_manager_listener_name"]


def firewall_manager_listener_name(firewall: str) -> str:
    """Return the name of the listener running ``firewall``'s authenticators.

    The qualifier it is aliased under, as
    :class:`~xtr_security_http.firewall.firewall_listener_interface.FirewallListenerInterface`,
    and what a ``@FirewallListenerOrder`` constraint names to order a listener
    against the firewall's own authentication step::

        @FirewallListenerOrder(after="security.manager_listener.api")
        class AuditListener(AbstractListener): ...
    """
    return f"security.manager_listener.{firewall}"
