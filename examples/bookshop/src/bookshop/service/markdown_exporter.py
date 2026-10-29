"""The markdown exporter, built through ``@autoconfigure(factory=...)``."""

from __future__ import annotations

from typing import Annotated, ClassVar, final

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_dependency_injection import Autowire, as_service, autoconfigure

from bookshop.service.exporter import Exporter, Rows

__all__ = ["MarkdownExporter", "build_markdown_exporter"]


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
