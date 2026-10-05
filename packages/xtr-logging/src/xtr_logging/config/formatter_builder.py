"""Turning a formatter configuration into a formatter."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from xtr_logging.exception.unknown_service_error import UnknownServiceError
from xtr_logging.formatter.console_formatter import ConsoleFormatter
from xtr_logging.formatter.json_batch_mode import JsonBatchMode
from xtr_logging.formatter.json_formatter import JsonFormatter
from xtr_logging.formatter.line_formatter import LineFormatter

from .formatter_configs import ConsoleFormatterConfig, JsonFormatterConfig, LineFormatterConfig

if TYPE_CHECKING:
    from xtr_logging.formatter.formatter_interface import FormatterInterface

    from .formatter_configs import FormatterConfig
    from .services import Services

__all__ = ["build_formatter"]


def build_formatter(config: FormatterConfig | str, services: Services) -> FormatterInterface:
    """Build the formatter ``config`` describes, or look up the service it names.

    Raises:
        UnknownServiceError: If ``config`` names a formatter that was not supplied.
    """
    match config:
        case str():
            found = services.formatters.get(config)
            if found is None:
                raise UnknownServiceError("formatter", config, tuple(services.formatters))
            return found
        case LineFormatterConfig():
            return LineFormatter(
                config.format,
                config.date_format,
                allow_inline_line_breaks=config.allow_inline_line_breaks,
                ignore_empty_context_and_extra=config.ignore_empty_context_and_extra,
                include_stacktraces=config.include_stacktraces,
            )
        case JsonFormatterConfig():
            return JsonFormatter(
                JsonBatchMode.NEWLINES if config.batch_mode == "newlines" else JsonBatchMode.JSON,
                append_newline=config.append_newline,
                ignore_empty_context_and_extra=config.ignore_empty_context_and_extra,
                include_stacktraces=config.include_stacktraces,
                date_format=config.date_format,
            )
        case ConsoleFormatterConfig():
            return ConsoleFormatter(
                config.format,
                config.date_format,
                include_stacktraces=config.include_stacktraces,
                colors=config.colors,
            )
        case _:
            # A configuration added to the union without a case fails here, not on a first record.
            assert_never(config)
