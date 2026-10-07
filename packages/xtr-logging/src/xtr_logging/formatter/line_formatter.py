"""One line of text per record."""

from __future__ import annotations

import re
import traceback
from typing import TYPE_CHECKING, Final

import msgspec
from typing_extensions import override

from ._text import class_name, previous_error, safe_str
from .formatter_interface import FormatterInterface
from .normalizer import Normalizer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.log_record import LogRecord

    from .normalizer import Normalized

__all__ = ["LineFormatter"]

_PLACEHOLDER_PATTERN: Final = (
    r"(?P<space> ?)%(?:(?P<bag>context|extra)\.(?P<key>[^%]+)"
    r"|(?P<name>datetime|channel|level_name|level|message|context|extra))%"
)
_TOKEN: Final = re.compile(_PLACEHOLDER_PATTERN)
"""Every token of a format, with the space before it — dropped with an empty bag's token."""
_LINE_BREAK: Final = re.compile(r"\r\n|\r|\n")
_TRAILING_SPACE: Final = re.compile(r"[ \t]+(?=\n|$)")
# C0 controls (bar tab and the line breaks handled above), DEL, and C1
# controls: an escape sequence like ``\x1b[2J`` could clear a terminal or
# forge a line, so it is stripped unless the caller opts to keep it.
_CONTROL: Final = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


class LineFormatter(FormatterInterface):
    """Renders a record by substituting ``%token%`` placeholders in a format.

    Tokens: ``%datetime%``, ``%channel%``, ``%level_name%``, ``%level%``,
    ``%message%``, ``%context%`` and ``%extra%`` — the latter two as JSON —
    plus ``%context.KEY%`` and ``%extra.KEY%`` for one entry, which is then
    left out of the JSON so it is not printed twice.

    Line breaks inside values become spaces unless
    ``allow_inline_line_breaks``, so one record stays one line and a log
    can be read with ``grep``. Other control characters — an escape sequence
    that could clear a terminal or forge a line — are stripped unless
    ``allow_control_characters``. An exception in context prints as
    ``[object] (Class: message at file:line)``.
    """

    SIMPLE_FORMAT: Final = "[%datetime%] %channel%.%level_name%: %message% %context% %extra%\n"

    __slots__: tuple[str, ...] = (
        "_allow_control_characters",
        "_allow_inline_line_breaks",
        "_format",
        "_ignore_empty",
        "_normalizer",
    )

    def __init__(  # noqa: PLR0913 — every line option is independent; all have defaults
        self,
        format: str | None = None,  # noqa: A002 — the name every formatter option uses
        date_format: str | None = None,
        *,
        allow_inline_line_breaks: bool = False,
        allow_control_characters: bool = False,
        ignore_empty_context_and_extra: bool = False,
        include_stacktraces: bool = False,
        max_depth: int | None = None,
        max_items: int | None = None,
    ) -> None:
        """Configure the line.

        Args:
            format: The template; :attr:`SIMPLE_FORMAT` when omitted.
            date_format: A :meth:`~datetime.datetime.strftime` format; ISO 8601
                when omitted.
            allow_inline_line_breaks: Keep line breaks inside values.
            allow_control_characters: Keep control characters inside values,
                rather than stripping the ones that could clear a terminal or
                forge a log line.
            ignore_empty_context_and_extra: Print nothing, rather than ``[]``,
                for an empty ``%context%`` or ``%extra%``.
            include_stacktraces: Print an exception's traceback after it. Turns
                on ``allow_inline_line_breaks``, which a traceback needs.
            max_depth: How deeply a nested value is rendered before it is cut;
                the normalizer's default when omitted.
            max_items: How many items of one collection are rendered; the
                normalizer's default when omitted.
        """
        self._format: str = format if format is not None else self.SIMPLE_FORMAT
        self._normalizer: Normalizer = _LineNormalizer(
            date_format,
            include_stacktraces=include_stacktraces,
            max_depth=max_depth,
            max_items=max_items,
        )
        self._allow_inline_line_breaks: bool = allow_inline_line_breaks or include_stacktraces
        self._allow_control_characters: bool = allow_control_characters
        self._ignore_empty: bool = ignore_empty_context_and_extra

    @override
    def format(self, record: LogRecord, /) -> str:
        """Render ``record`` as one line — or more, if line breaks are allowed."""
        context = _as_dict(self._normalizer.normalize(record.context))
        extra = _as_dict(self._normalizer.normalize(record.extra))
        bags = {"context": context, "extra": extra}

        # A keyed entry leaves its bag before the bag is printed; one named
        # twice, or not there at all, prints nothing.
        keyed: list[str] = []
        for match in _TOKEN.finditer(self._format):
            bag = match.group("bag")
            if bag is not None:
                source, key = bags[bag], match.group("key")
                keyed.append(self._stringify(source.pop(key)) if key in source else "")

        values: dict[str, str] = {
            "datetime": self._normalizer.format_datetime(record.datetime),
            "channel": self._stringify(record.channel),
            "level_name": self._level_name(record),
            "level": str(record.level.value),
            "message": self._stringify(record.message),
            "context": self._stringify_bag(context),
            "extra": self._stringify_bag(extra),
        }
        entries = iter(keyed)

        def substitute(match: re.Match[str]) -> str:
            name = match.group("name")
            if name is None:
                entry = next(entries)
                return match.group("space") + entry if entry else ""
            if self._ignore_empty and name in bags and not bags[name]:
                return ""
            return match.group("space") + values[name]

        # One pass over the format: what a value brings in is never read as a token.
        output = _TOKEN.sub(substitute, self._format)
        if self._ignore_empty:
            output = _TRAILING_SPACE.sub("", output)
        return output

    @override
    def format_batch(self, records: Sequence[LogRecord], /) -> str:
        """Render each record and join them."""
        return "".join(self.format(record) for record in records)

    def _level_name(self, record: LogRecord) -> str:
        """Return what ``%level_name%`` prints for ``record``."""
        return record.level_name

    def _stringify_bag(self, values: dict[str, Normalized]) -> str:
        if not values:
            return "" if self._ignore_empty else "[]"
        return self._stringify(values)

    def _stringify(self, value: Normalized) -> str:
        text = value if isinstance(value, str) else msgspec.json.encode(value).decode()
        if not self._allow_control_characters:
            text = _CONTROL.sub("", text)
        if self._allow_inline_line_breaks:
            return text
        return _LINE_BREAK.sub(" ", text)


class _LineNormalizer(Normalizer):
    """Prints an exception as one string rather than a nested structure."""

    @override
    def _normalize_exception(self, error: BaseException, depth: int) -> Normalized:
        text = f"[object] ({_describe(error)})"
        # A chain may loop — an error raised from one that has it as context —
        # so every error is told once, and the chain is cut at the depth limit.
        seen = {id(error)}
        previous = previous_error(error)
        while previous is not None and id(previous) not in seen and len(seen) < self.max_depth:
            seen.add(id(previous))
            text += f"\n[previous exception] [object] ({_describe(previous)})"
            previous = previous_error(previous)
        if self.include_stacktraces and error.__traceback__ is not None:
            text += "\n[stacktrace]\n" + "".join(traceback.format_tb(error.__traceback__))
        return text


def _describe(error: BaseException) -> str:
    frames = traceback.extract_tb(error.__traceback__)
    origin = f" at {frames[-1].filename}:{frames[-1].lineno}" if frames else ""
    return f"{class_name(error)}: {safe_str(error)}{origin}"


def _as_dict(value: Normalized) -> dict[str, Normalized]:
    return value if isinstance(value, dict) else {}
