"""Exporters by format, resolved lazily through a ``ServiceLocator``."""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from typing import final

from xtr_dependency_injection import ServiceKey, ServiceLocator, as_service
from xtr_service_contracts import ContainerInterface

from .exporters import Exporter, Rows

__all__ = ["ExportRegistry"]


@final
@as_service
class ExportRegistry:
    """Builds only the exporter a format asks for.

    ``formats`` is not injected: ``ExporterRegistryPass`` computes it at compile time from
    the ``bookshop.exporter`` tags and sets it as an argument on this definition. The
    :class:`ServiceLocator` then builds an exporter only when its format is asked for.
    """

    __slots__ = ("_locator",)

    def __init__(
        self, container: ContainerInterface, formats: Mapping[Hashable, ServiceKey]
    ) -> None:
        """Look exporters up in ``container`` by the keys ``formats`` maps them to."""
        self._locator = ServiceLocator[Exporter](container, formats)

    def formats(self) -> tuple[str, ...]:
        """Every format there is an exporter for."""
        return tuple(str(name) for name in self._locator.provided_services())

    async def export(self, format_name: str, rows: Rows) -> str:
        """Render ``rows`` as ``format_name``.

        Raises:
            UnknownLocatorKeyError: If no exporter serves ``format_name`` — a ``LookupError``.
        """
        exporter = await self._locator.get(format_name)
        return exporter.export(rows)
