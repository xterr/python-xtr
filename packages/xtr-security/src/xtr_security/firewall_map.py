"""The firewalls of an application: found by name, matched, and read for their config.

The bundle gathers each firewall into a
:class:`~xtr_security.firewall_context.FirewallContext`, pairs it with the request
matcher its :class:`~xtr_security.firewall_config.FirewallConfig` describes, and
holds the three in this map. It is what the HTTP edge injects as a
:class:`~xtr_security_http.firewall_map_interface.FirewallMapInterface`, adding to
that contract :meth:`get_firewall_config`, which the :class:`Security` facade reads
to answer which firewall claims a request.

The HTTP edge ships its own matcher-only
:class:`~xtr_security_http.firewall_map.FirewallMap` so it runs without the bundle;
this one is the bundle's, built from the configured firewalls and their contexts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_http.firewall_map import FirewallMap as HttpFirewallMap
from xtr_security_http.firewall_map_interface import FirewallMapInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request
    from xtr_security_http.firewall_context_interface import FirewallContextInterface
    from xtr_security_http.request_matcher.request_matcher_interface import RequestMatcherInterface

    from xtr_security.firewall_config import FirewallConfig

__all__ = ["FirewallMap"]

#: One firewall: the matcher that claims its requests, the context that runs it,
#: and the configuration it was built from.
FirewallEntry = tuple["RequestMatcherInterface", "FirewallContextInterface", "FirewallConfig"]


@final
class FirewallMap(FirewallMapInterface):
    """The application's firewalls, found by name, matched, and read for their config.

    Each firewall is the matcher that claims its requests, the context that runs
    it, and the configuration it came from. Finding by name and matching a
    request are delegated to the HTTP edge's own map over the same contexts, so
    the two share one matching behaviour; this map adds
    :meth:`get_firewall_config`, the firewall configuration a request resolves to.
    """

    __slots__ = ("_configs", "_inner")

    def __init__(self, firewalls: Sequence[FirewallEntry] = ()) -> None:
        """Record the firewalls, delegating name and request matching to the HTTP map.

        Raises:
            InvalidArgumentError: When two firewalls share a name.
        """
        self._inner = HttpFirewallMap([(matcher, context) for matcher, context, _ in firewalls])
        self._configs: tuple[tuple[RequestMatcherInterface, FirewallConfig], ...] = tuple(
            (matcher, config) for matcher, _, config in firewalls
        )

    @override
    def has(self, name: str) -> bool:
        """Tell whether a firewall is registered under ``name``."""
        return self._inner.has(name)

    @override
    def get(self, name: str) -> FirewallContextInterface:
        """Return the firewall named ``name``.

        Raises:
            UnknownFirewallError: When no firewall carries that name.
        """
        return self._inner.get(name)

    @override
    def match(self, request: Request) -> FirewallContextInterface | None:
        """Return the first firewall whose matcher claims ``request``, or ``None``."""
        return self._inner.match(request)

    @override
    def names(self) -> tuple[str, ...]:
        """Return the names of every firewall registered."""
        return self._inner.names()

    def get_firewall_config(self, request: Request) -> FirewallConfig | None:
        """Return the configuration of the firewall that claims ``request``, or ``None``."""
        for matcher, config in self._configs:
            if matcher.matches(request):
                return config
        return None
