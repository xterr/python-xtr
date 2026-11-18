from __future__ import annotations

from typing import TYPE_CHECKING, Self, cast, final

from xtr_http_kernel.data_collector import DATA_COLLECTOR_TAG

from xtr_http_client.bundle._profiler import register_profiler
from xtr_http_client.data_collector import HttpClientDataCollector

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator


@final
class _Services:
    """Notes what is registered, and the tags it is given."""

    def __init__(self) -> None:
        self.registered: list[object] = []
        self.tags: list[tuple[str, dict[str, object]]] = []

    def set(self, target: object) -> Self:
        self.registered.append(target)
        return self

    def add_tag(self, tag: str, /, **attributes: object) -> Self:
        self.tags.append((tag, attributes))
        return self


def test_the_collector_is_registered_as_the_http_client_panel() -> None:
    services = _Services()

    register_profiler(cast("ServiceConfigurator", cast("object", services)))

    assert services.registered == [HttpClientDataCollector]
    assert services.tags == [
        (
            DATA_COLLECTOR_TAG,
            {
                "name": "http_client",
                "template": "@xtr_http_client/collector/http_client.html.j2",
                "priority": 250,
            },
        )
    ]
