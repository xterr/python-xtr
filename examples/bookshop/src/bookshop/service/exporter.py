"""The base of every exporter, tagged by its base class through ``@autoconfigure(tags=...)``."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import ClassVar, Final

from xtr_dependency_injection import autoconfigure

__all__ = ["EXPORTER_TAG", "Exporter", "Rows"]

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
