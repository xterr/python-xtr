"""Formatters as configuration: the ``formatter:`` entry of a handler."""

from __future__ import annotations

from typing import Literal, TypeAlias

import msgspec

__all__ = [
    "ConsoleFormatterConfig",
    "FormatterConfig",
    "JsonFormatterConfig",
    "LineFormatterConfig",
]


class _FormatterConfigBase(
    msgspec.Struct,
    frozen=True,
    kw_only=True,
    forbid_unknown_fields=True,
    tag_field="type",
):
    date_format: str | None = None
    include_stacktraces: bool = False


class LineFormatterConfig(_FormatterConfigBase, frozen=True, kw_only=True, tag="line"):
    """A :class:`~xtr_logging.formatter.line_formatter.LineFormatter`."""

    format: str | None = None
    allow_inline_line_breaks: bool = False
    ignore_empty_context_and_extra: bool = False


class JsonFormatterConfig(_FormatterConfigBase, frozen=True, kw_only=True, tag="json"):
    """A :class:`~xtr_logging.formatter.json_formatter.JsonFormatter`."""

    batch_mode: Literal["json", "newlines"] = "newlines"
    append_newline: bool = True
    ignore_empty_context_and_extra: bool = False


class ConsoleFormatterConfig(_FormatterConfigBase, frozen=True, kw_only=True, tag="console"):
    """A :class:`~xtr_logging.formatter.console_formatter.ConsoleFormatter`."""

    format: str | None = None
    colors: bool = False


FormatterConfig: TypeAlias = LineFormatterConfig | JsonFormatterConfig | ConsoleFormatterConfig
"""Any built-in formatter, told apart by its ``type``."""
