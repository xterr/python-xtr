"""Real service locators over fixed services, as a container would hand them over."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from xtr_dependency_injection import ServiceLocator

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

    from xtr_service_contracts import ContainerInterface

__all__ = ["locator"]


@final
class _FixedContainer:
    """A container answering ``get`` from a fixed mapping, by qualifier."""

    def __init__(self, services: Mapping[str, object]) -> None:
        self._services = dict(services)

    async def get(self, service: type[object], qualifier: Hashable | None = None) -> object:
        del service
        return self._services[cast("str", qualifier)]

    def has(self, service: type[object], qualifier: Hashable | None = None) -> bool:
        del service
        return qualifier in self._services

    def get_parameter(self, name: str) -> object:  # pragma: no cover - unused by a locator
        raise KeyError(name)

    def has_parameter(self, name: str) -> bool:  # pragma: no cover - unused by a locator
        del name
        return False


def locator[T](interface: type[T], services: Mapping[str, T]) -> ServiceLocator[T]:
    """Build a locator naming each of ``services`` by its key, as ``interface``."""
    container = cast("ContainerInterface", cast("object", _FixedContainer(services)))
    entries: Mapping[Hashable, tuple[type, str | None]] = {
        name: (interface, name) for name in services
    }
    return ServiceLocator(container, entries)
