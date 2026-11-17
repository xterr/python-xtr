"""The security panel of the profiler, registered when the http kernel profiles requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_event_dispatcher.bundle import EventDispatcherConfig
from xtr_http_kernel.data_collector import DATA_COLLECTOR_TAG

from xtr_security.data_collector import SecurityDataCollector

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = ["register_profiler"]

_NAME: Final = "security"
_TEMPLATE: Final = "@xtr_security/collector/security.html.j2"
_PRIORITY: Final = 270


def register_profiler(
    services: ServiceConfigurator, builder: ContainerBuilder, *, votes_traced: bool
) -> None:
    """Register the ``security`` collector, for the traced decorations to report to.

    The decision manager is traced when ``votes_traced``; the firewalls'
    manager listeners are traced on the event dispatcher bundle's ``trace``
    setting — in debug mode unless the application chose — the trigger the
    bundle's tracing pass reads too. The traced decorations are handed the
    collector wherever its definition is registered.
    """
    trace = builder.get_extension_config(EventDispatcherConfig).trace
    collector = SecurityDataCollector(
        votes_traced=votes_traced,
        authenticators_traced=(
            trace if trace is not None else bool(builder.get_parameter("kernel.debug"))
        ),
    )
    _ = services.instance(collector).add_tag(
        DATA_COLLECTOR_TAG, name=_NAME, template=_TEMPLATE, priority=_PRIORITY
    )
