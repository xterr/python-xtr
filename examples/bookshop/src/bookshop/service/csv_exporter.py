"""The CSV exporter, tagged through its base class."""

from __future__ import annotations

import csv
import io
from typing import ClassVar, final

from typing_extensions import override
from xtr_dependency_injection import as_service

from bookshop.service.exporter import Exporter, Rows

__all__ = ["CsvExporter"]


@final
@as_service
class CsvExporter(Exporter):
    """Comma-separated values."""

    format_name: ClassVar[str] = "csv"

    @override
    def export(self, rows: Rows) -> str:
        if not rows:
            return ""
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()
