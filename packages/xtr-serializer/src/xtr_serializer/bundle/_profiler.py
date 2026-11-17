"""The serializer's profiler panel, registered when the http kernel profiles requests.

Imported only then, so xtr-http-kernel and xtr-clock stay optional. Every factory here is read by
the container, so the types its parameters name are imported at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final

from xtr_dependency_injection import Target
from xtr_http_kernel.data_collector import DATA_COLLECTOR_TAG, RequestTrace

from xtr_serializer.data_collector.serializer_call import SerializerCall
from xtr_serializer.data_collector.serializer_data_collector import SerializerDataCollector
from xtr_serializer.data_collector.traceable_serializer import TraceableSerializer
from xtr_serializer.serializer import Serializer

from .serializer_config import DEFAULT_SERIALIZER

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from xtr_dependency_injection import ServiceConfigurator

__all__ = ["register_profiler"]

_NAME: Final = "serializer"
_TEMPLATE: Final = "@xtr_serializer/collector/serializer.html.j2"
_PRIORITY: Final = 210

_TRACE: Final[RequestTrace[SerializerCall]] = RequestTrace("serializer_calls")
"""The one trace every traced serializer records into and the collector reads."""


def register_profiler(
    services: ServiceConfigurator, qualifiers: Iterable[str | None]
) -> type[TraceableSerializer]:
    """Register the collector, and a traced serializer beside each of ``qualifiers``.

    Returns the class the bundle aliases the serializer interfaces to instead of
    :class:`~xtr_serializer.Serializer`, under the same qualifiers. The traced serializer is a
    service of its own rather than a decoration of the serializer's key: that key's class is
    final, and a decoration must be one of it.
    """
    _ = services.set(_collector).add_tag(
        DATA_COLLECTOR_TAG, name=_NAME, template=_TEMPLATE, priority=_PRIORITY
    )
    for qualifier in qualifiers:
        _ = services.set(_traceable_factory(qualifier), qualifier=qualifier)
    return TraceableSerializer


def _collector() -> SerializerDataCollector:
    return SerializerDataCollector(_TRACE)


def _traceable_factory(qualifier: str | None) -> Callable[..., TraceableSerializer]:
    """Build the factory tracing the serializer ``qualifier`` names, under its configured name."""
    name = DEFAULT_SERIALIZER if qualifier is None else qualifier

    def traceable_serializer(serializer: Serializer) -> TraceableSerializer:
        return TraceableSerializer(serializer, name, _TRACE)

    if qualifier is not None:
        # The qualifier is known only here, so the annotation naming it is written at runtime.
        traceable_serializer.__annotations__ = {
            "serializer": Annotated[Serializer, Target(qualifier)],
            "return": TraceableSerializer,
        }
    return traceable_serializer
