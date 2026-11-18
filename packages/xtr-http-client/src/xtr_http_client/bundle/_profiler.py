"""The http client's profiler panel, registered while the http kernel profiles requests.

Imported only once the http kernel's bundle is active with its profiler on,
which proves xtr-http-kernel installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_http_kernel.data_collector import DATA_COLLECTOR_TAG

from xtr_http_client.data_collector import HttpClientDataCollector

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator

__all__ = ["register_profiler"]

_NAME: Final = "http_client"
_TEMPLATE: Final = "@xtr_http_client/collector/http_client.html.j2"
_PRIORITY: Final = 250


def register_profiler(services: ServiceConfigurator) -> None:
    """Register the collector every client hands its requests to while one is profiled."""
    _ = services.set(HttpClientDataCollector).add_tag(
        DATA_COLLECTOR_TAG, name=_NAME, template=_TEMPLATE, priority=_PRIORITY
    )
