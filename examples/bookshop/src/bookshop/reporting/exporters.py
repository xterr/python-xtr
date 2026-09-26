"""Exporters, tagged by their base class; one built through ``@autoconfigure(factory=...)``."""

from __future__ import annotations

import csv
import io
import json
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Annotated, ClassVar, Final, final

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_dependency_injection import Autowire, as_service, autoconfigure

__all__ = [
    "EXPORTER_TAG",
    "CsvExporter",
    "Exporter",
    "JsonExporter",
    "MarkdownExporter",
    "build_markdown_exporter",
]

EXPORTER_TAG: Final = "bookshop.exporter"

Rows = Sequence[Mapping[str, str]]


def _format_of(exporter: type) -> Mapping[str, object]:
    """The tag's ``format`` attribute, read off the concrete class the rule matched."""
    return {"format": getattr(exporter, "format_name", exporter.__name__.lower())}


@autoconfigure(tags=[(EXPORTER_TAG, _format_of)])
class Exporter(ABC):
    """Renders rows in one format; every registered subclass is tagged with its format."""

    format_name: ClassVar[str]

    @abstractmethod
    def export(self, rows: Rows) -> str:
        """Render ``rows``."""


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


@final
@as_service
class JsonExporter(Exporter):
    """One JSON array."""

    format_name: ClassVar[str] = "json"

    @override
    def export(self, rows: Rows) -> str:
        return json.dumps(list(rows), indent=2)


def build_markdown_exporter(
    shop: Annotated[str, Autowire(param="shop.name")],
    clock: ClockInterface,
) -> MarkdownExporter:
    """Build the markdown exporter with a title computed at build time.

    ``@autoconfigure(factory=...)`` below turns the class definition into a factory
    definition using this function; its return type must be exactly the matched class.
    """
    return MarkdownExporter(f"{shop} — {clock.now():%Y-%m-%d}")


@final
@autoconfigure(factory=build_markdown_exporter)
@as_service
class MarkdownExporter(Exporter):
    """A markdown table under a title.

    Its constructor takes a plain string, so the container builds it through
    :func:`build_markdown_exporter` instead.
    """

    format_name: ClassVar[str] = "markdown"

    def __init__(self, title: str) -> None:
        """Title the table ``title``."""
        self._title = title

    @override
    def export(self, rows: Rows) -> str:
        if not rows:
            return f"# {self._title}\n"
        headers = list(rows[0])
        lines = [
            f"# {self._title}",
            "",
            "| " + " | ".join(headers) + " |",
            "|" + "---|" * len(headers),
            *("| " + " | ".join(row[h] for h in headers) + " |" for row in rows),
        ]
        return "\n".join(lines) + "\n"
