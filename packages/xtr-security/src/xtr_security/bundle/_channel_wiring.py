"""The channel step a firewall with channel rules redirects by.

A rule that names a channel demands its requests arrive over that scheme;
 the step built here answers one arriving over the other with a redirect to
the same request over the scheme the rule demands. It is parked first on
the chain — ahead of the context step and the manager's own — so nothing a
request carries is spent before it arrives the way the rule demands. The
ports the redirect spells out are the application's configured ones: this
stack has no router to read them from the request's own context, so a
non-default port is named where the application configured it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.bridge import StarletteHttpFactoryInterface
from xtr_http_message_contracts.factory import ResponseFactoryInterface
from xtr_security_http import ChannelListener

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator
    from xtr_security_http.access_map import AccessMap

__all__ = ["firewall_channel_listener_name", "register_channel_listener"]


def firewall_channel_listener_name(firewall_name: str) -> str:
    """The qualifier of a firewall's channel chain step."""
    return f"{firewall_name}#channel_listener"


def register_channel_listener(
    services: ServiceConfigurator,
    name: str,
    access_map: AccessMap,
    *,
    http_port: int,
    https_port: int,
) -> str:
    """Register the channel step over the firewall's rules, and return its qualifier.

    The step is aliased under the firewall listener interface and parked
    first on the chain, ahead of the context step and the manager's own: a
    request arriving over the wrong scheme is redirected before anything it
    carries is restored, authenticated or decided.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's chain-step import
        FirewallListenerInterface,
    )

    qualifier = firewall_channel_listener_name(name)

    def channel_listener(
        responses: ResponseFactoryInterface,
        bridge: StarletteHttpFactoryInterface,
    ) -> ChannelListener:
        """Build the step over the firewall's rules and what it answers with."""
        return ChannelListener(
            access_map,
            responses,
            bridge,
            http_port=http_port,
            https_port=https_port,
        )

    channel_listener.__annotations__ = {
        "responses": ResponseFactoryInterface,
        "bridge": StarletteHttpFactoryInterface,
        "return": ChannelListener,
    }
    channel_listener.__name__ = f"channel_listener_{name}"
    channel_listener.__qualname__ = channel_listener.__name__
    _ = services.set(channel_listener, qualifier=qualifier, lifetime="scoped")
    services.alias(
        FirewallListenerInterface,
        ChannelListener,
        alias_qualifier=qualifier,
        target_qualifier=qualifier,
    )
    return qualifier
