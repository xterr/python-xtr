"""Refusing a stateful firewall whose session storage never arrived.

The context listener of a stateful firewall is registered with the
container's remove-if-missing marker over the application's
``SessionStorageInterface`` service: with no storage registered, the marker
drops the listener — and the firewall's chain would name a listener that is
not there. This pass runs between that drop and the chain sorting, and turns
it into a refusal naming the missing service, so an application that asked
for a stateful firewall learns what to register instead of learning a
qualifier only the bundle knows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_http.firewall.firewall_listener_interface import (
    FirewallListenerInterface,
)

from xtr_security.bundle._stateful_wiring import context_listener_name
from xtr_security.exception import InvalidConfigurationError

from .firewall_context import FirewallContext
from .security_config import SecurityConfig

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder

__all__ = ["RefuseStatefulFirewallsWithoutSessionStoragePass"]


@final
class RefuseStatefulFirewallsWithoutSessionStoragePass:
    """Fails the build for a stateful firewall with no session storage registered.

    The security bundle registers this after the container's
    remove-if-missing pass has settled and before the firewall chains are
    sorted, so the refusal is heard before any chain is ordered.
    """

    __slots__ = ()

    def process(self, builder: ContainerBuilder) -> None:
        """Refuse every stateful firewall whose context listener was dropped.

        Raises:
            InvalidConfigurationError: When a stateful firewall's context
                listener is gone — no ``SessionStorageInterface`` service is
                registered for it to store sessions through.
        """
        for name, firewall in builder.get_extension_config(SecurityConfig).firewalls.items():
            if firewall.stateless or not firewall.security:
                continue
            if not builder.has_definition(FirewallContext, name):
                continue
            # Alias-aware on purpose: the remove-if-missing sweep takes the
            # chain alias with the definition it pointed at.
            if builder.has(FirewallListenerInterface, context_listener_name(name)):
                continue
            raise InvalidConfigurationError(
                f'The firewall "{name}" is configured stateful but no '
                "SessionStorageInterface service is registered; register one — "
                "the session machinery stores its contexts through it.",
            )
