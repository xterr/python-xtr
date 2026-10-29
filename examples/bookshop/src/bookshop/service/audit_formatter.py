"""The formatter the logging config names by id — see ``memory_handler`` for every id."""

from __future__ import annotations

from xtr_dependency_injection import as_service
from xtr_logging import FormatterInterface, JsonBatchMode, JsonFormatter

__all__ = ["audit_formatter"]


@as_service(qualifier="audit_json")
def audit_formatter() -> FormatterInterface:
    """Render audit records as JSON lines; the ``audit_file`` handler names it as a string."""
    return JsonFormatter(JsonBatchMode.NEWLINES, include_stacktraces=True)
