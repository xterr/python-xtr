"""A compiler pass at ``OPTIMIZE``: it hands the export registry its exporters, by format."""

from __future__ import annotations

from collections.abc import Hashable
from typing import final

from typing_extensions import override
from xtr_dependency_injection import (
    CompilerPassInterface,
    ContainerBuilder,
    PassStage,
    ServiceKey,
    compiler_pass,
)

from bookshop.service.export_registry import ExportRegistry
from bookshop.service.exporter import EXPORTER_TAG

__all__ = ["ExporterRegistryPass"]


@final
@compiler_pass(stage=PassStage.OPTIMIZE, priority=-100)
class ExporterRegistryPass(CompilerPassInterface):
    """Finds every tagged exporter and hands the registry their keys, by format.

    ``OPTIMIZE``, after autoconfiguration has tagged every ``Exporter`` subclass.
    """

    @override
    def process(self, builder: ContainerBuilder) -> None:
        formats: dict[Hashable, ServiceKey] = {}
        for key, attributes in builder.find_tagged_service_ids(EXPORTER_TAG).items():
            for attribute in attributes:
                formats[str(attribute["format"])] = key
        _ = builder.get_definition(ExportRegistry).set_argument("formats", formats)
        builder.log(self, f"exporters: {', '.join(sorted(map(str, formats)))}")
