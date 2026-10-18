"""Traces every firewall's manager listener, as the firewalls' dispatchers are traced."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final, cast, final

from xtr_dependency_injection import Definition, Origin, Target
from xtr_event_dispatcher.bundle import EventDispatcherConfig
from xtr_security_http import (
    AuthenticatorManagerListener,
    FirewallListenerInterface,
    TraceableAuthenticatorManagerListener,
)

from .firewall_context import FirewallContext
from .firewall_manager_listener_name import firewall_manager_listener_name
from .security_config import SecurityConfig

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from xtr_dependency_injection import ContainerBuilder

__all__ = ["MakeFirewallsManagerListenerTraceablePass"]

_ORIGIN: Final = Origin("bundle", "security")


@final
class MakeFirewallsManagerListenerTraceablePass:
    """Swaps each firewall's manager listener for a traceable one when tracing.

    Tracing follows the event dispatcher bundle's ``trace`` setting — in debug
    mode unless the application chose — the same trigger that traces the
    firewalls' dispatchers, so a traced firewall's chain explains its
    authentication: the traceable listener wraps each authenticator the
    supports pass chose, and the tooling reads what they recorded.

    The swap happens on the chain the context parks — the plain listener's
    qualifier gives way to the traceable one's, the same argument the sorting
    pass orders — so the plain listener stays registered for the traceable
    one to wrap, and the chain resolves the wrapper alone.
    """

    __slots__ = ()

    def process(self, builder: ContainerBuilder) -> None:
        """Swap each firewall's manager listener for a traceable one, when tracing is on."""
        trace = builder.get_extension_config(EventDispatcherConfig).trace
        if not (trace if trace is not None else bool(builder.get_parameter("kernel.debug"))):
            return

        for firewall in builder.get_extension_config(SecurityConfig).firewalls:
            plain = firewall_manager_listener_name(firewall)
            if not builder.has_definition(FirewallContext, firewall):
                continue
            definition = builder.get_definition(FirewallContext, firewall)
            arguments = definition.get_arguments()
            if "listeners" not in arguments:
                continue
            parked = cast("Sequence[str]", arguments["listeners"])
            if plain not in parked:
                continue
            traceable = f"security.traceable_manager_listener.{firewall}"
            builder.set_alias(
                FirewallListenerInterface,
                TraceableAuthenticatorManagerListener,
                alias_qualifier=traceable,
                target_qualifier=traceable,
            )
            _ = builder.set_definition(
                Definition(
                    (TraceableAuthenticatorManagerListener, traceable),
                    _traceable_listener_factory(plain),
                    "factory",
                    "scoped",
                    _ORIGIN,
                )
            )
            _ = definition.set_argument(
                "listeners",
                tuple(traceable if qualifier == plain else qualifier for qualifier in parked),
            )


def _traceable_listener_factory(
    plain: str,
) -> Callable[..., TraceableAuthenticatorManagerListener]:
    """Return the factory wrapping the firewall's manager listener in a trace."""

    def traceable_manager_listener(
        listener: AuthenticatorManagerListener,
    ) -> TraceableAuthenticatorManagerListener:
        """Trace the manager listener the chain would otherwise run."""
        return TraceableAuthenticatorManagerListener(listener)

    traceable_manager_listener.__annotations__ = {
        "listener": Annotated[AuthenticatorManagerListener, Target(plain)],
        "return": TraceableAuthenticatorManagerListener,
    }
    traceable_manager_listener.__name__ = f"traceable_manager_listener_{plain}"
    traceable_manager_listener.__qualname__ = traceable_manager_listener.__name__
    return traceable_manager_listener
