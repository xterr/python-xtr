"""Turning a formatter spec into a formatter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_logging.exception.unknown_service_error import UnknownServiceError
from xtr_logging.formatter.console_formatter import ConsoleFormatter
from xtr_logging.formatter.json_batch_mode import JsonBatchMode
from xtr_logging.formatter.json_formatter import JsonFormatter
from xtr_logging.formatter.line_formatter import LineFormatter

from .formatter_specs import ConsoleFormatterSpec, JsonFormatterSpec, LineFormatterSpec

if TYPE_CHECKING:
    from xtr_logging.formatter.formatter_interface import FormatterInterface

    from .formatter_specs import FormatterSpec
    from .services import Services

__all__ = ["build_formatter"]


def build_formatter(spec: FormatterSpec | str, services: Services) -> FormatterInterface:
    """Build the formatter ``spec`` describes, or look up the service it names.

    Raises:
        UnknownServiceError: If ``spec`` names a formatter that was not supplied.
    """
    match spec:
        case str():
            found = services.formatters.get(spec)
            if found is None:
                raise UnknownServiceError("formatter", spec, tuple(services.formatters))
            return found
        case LineFormatterSpec():
            return LineFormatter(
                spec.format,
                spec.date_format,
                allow_inline_line_breaks=spec.allow_inline_line_breaks,
                ignore_empty_context_and_extra=spec.ignore_empty_context_and_extra,
                include_stacktraces=spec.include_stacktraces,
            )
        case JsonFormatterSpec():
            return JsonFormatter(
                JsonBatchMode.NEWLINES if spec.batch_mode == "newlines" else JsonBatchMode.JSON,
                append_newline=spec.append_newline,
                ignore_empty_context_and_extra=spec.ignore_empty_context_and_extra,
                include_stacktraces=spec.include_stacktraces,
                date_format=spec.date_format,
            )
        case ConsoleFormatterSpec():
            return ConsoleFormatter(
                spec.format,
                spec.date_format,
                include_stacktraces=spec.include_stacktraces,
                colors=spec.colors,
            )
