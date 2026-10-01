"""Traces every firewall's dispatcher, as the event dispatcher bundle traces its own."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_dependency_injection import Definition, Origin, bundle_active
from xtr_event_dispatcher import EventDispatcherInterface
from xtr_event_dispatcher.bundle import EventDispatcherConfig, traceable_event_dispatcher_factory
from xtr_event_dispatcher.debug import TraceableEventDispatcher

from .firewall_dispatcher_name import firewall_dispatcher_name
from .security_config import SecurityConfig

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder

__all__ = ["MakeFirewallsEventDispatcherTraceablePass"]

_ORIGIN: Final = Origin("bundle", "security")


@final
class MakeFirewallsEventDispatcherTraceablePass:
    """Wraps every firewall's dispatcher in a :class:`TraceableEventDispatcher` when tracing.

    Tracing follows the event dispatcher bundle's ``trace`` setting — in debug
    mode unless the application chose — so the firewalls' security events are
    traced, timed and logged to the ``"event"`` channel like every other
    event. Each trace is reset between units of work.
    """

    __slots__ = ()

    def process(self, builder: ContainerBuilder) -> None:
        """Decorate each firewall's dispatcher with a trace, when tracing is on."""
        trace = builder.get_extension_config(EventDispatcherConfig).trace
        if not (trace if trace is not None else bool(builder.get_parameter("kernel.debug"))):
            return

        factory = traceable_event_dispatcher_factory(logged=bundle_active(builder, "logging"))
        for firewall in builder.get_extension_config(SecurityConfig).firewalls:
            name = firewall_dispatcher_name(firewall)
            if not builder.has_definition(EventDispatcherInterface, name):
                continue
            definition = Definition(
                (TraceableEventDispatcher, name), factory, "factory", "singleton", _ORIGIN
            )
            _ = (
                builder.set_definition(definition)
                .set_decorated_service(EventDispatcherInterface, qualifier=name)
                .add_tag("kernel.reset", method="reset")
            )
