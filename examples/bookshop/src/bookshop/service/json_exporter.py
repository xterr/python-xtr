"""The JSON exporter, tagged through its base class."""

from __future__ import annotations

import json
from typing import ClassVar, final

from typing_extensions import override
from xtr_dependency_injection import as_service

from bookshop.service.exporter import Exporter, Rows

__all__ = ["JsonExporter"]


@final
@as_service
class JsonExporter(Exporter):
    """One JSON array."""

    format_name: ClassVar[str] = "json"

    @override
    def export(self, rows: Rows) -> str:
        return json.dumps(list(rows), indent=2)
