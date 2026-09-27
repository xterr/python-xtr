"""One line of text per record."""

from __future__ import annotations

import re
import traceback
from typing import TYPE_CHECKING, Final

import msgspec
from typing_extensions import override

from ._text import class_name, safe_str
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


class LineFormatter(FormatterInterface):
    """Renders a record by substituting ``%token%`` placeholders in a format.

    Tokens: ``%datetime%``, ``%channel%``, ``%level_name%``, ``%level%``,
    ``%message%``, ``%context%`` and ``%extra%`` — the latter two as JSON —
    plus ``%context.KEY%`` and ``%extra.KEY%`` for one entry, which is then
    left out of the JSON so it is not printed twice.

    Line breaks inside values become spaces unless
    ``allow_inline_line_breaks``, so one record stays one line and a log
    can be read with ``grep``. An exception in context prints as
    ``[object] (Class: message at file:line)``.
    """

    SIMPLE_FORMAT: Final = "[%datetime%] %channel%.%level_name%: %message% %context% %extra%\n"

    def __init__(
        self,
        format: str | None = None,  # noqa: A002 — the name every formatter option uses
        date_format: str | None = None,
        *,
        allow_inline_line_breaks: bool = False,
        ignore_empty_context_and_extra: bool = False,
        include_stacktraces: bool = False,
    ) -> None:
        """Configure the line.

        Args:
            format: The template; :attr:`SIMPLE_FORMAT` when omitted.
            date_format: A :meth:`~datetime.datetime.strftime` format; ISO 8601
                when omitted.
            allow_inline_line_breaks: Keep line breaks inside values.
            ignore_empty_context_and_extra: Print nothing, rather than ``[]``,
                for an empty ``%context%`` or ``%extra%``.
            include_stacktraces: Print an exception's traceback after it. Turns
                on ``allow_inline_line_breaks``, which a traceback needs.
        """
        self._format: str = format if format is not None else self.SIMPLE_FORMAT
        self._normalizer: Normalizer = _LineNormalizer(
            date_format, include_stacktraces=include_stacktraces
        )
        self._allow_inline_line_breaks: bool = allow_inline_line_breaks or include_stacktraces
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
            "channel": record.channel,
            "level_name": record.level_name,
            "level": str(record.level.value),
            "message": self._stringify(record.message),
            "context": self._stringify_bag(context),
            "extra": self._stringify_bag(extra),
        }
        entries = iter(keyed)

        def substitute(match: re.Match[str]) -> str:
            name = match.group("name")
            if name is None:
                return match.group("space") + next(entries)
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

    def _stringify_bag(self, values: dict[str, Normalized]) -> str:
        if not values:
            return "" if self._ignore_empty else "[]"
        return self._stringify(values)

    def _stringify(self, value: Normalized) -> str:
        text = value if isinstance(value, str) else msgspec.json.encode(value).decode()
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
        previous = _previous(error)
        while previous is not None and id(previous) not in seen and len(seen) < self.max_depth:
            seen.add(id(previous))
            text += f"\n[previous exception] [object] ({_describe(previous)})"
            previous = _previous(previous)
        if self.include_stacktraces and error.__traceback__ is not None:
            text += "\n[stacktrace]\n" + "".join(traceback.format_tb(error.__traceback__))
        return text


def _describe(error: BaseException) -> str:
    frames = traceback.extract_tb(error.__traceback__)
    origin = f" at {frames[-1].filename}:{frames[-1].lineno}" if frames else ""
    return f"{class_name(error)}: {safe_str(error)}{origin}"


def _previous(error: BaseException) -> BaseException | None:
    return error.__cause__ or (None if error.__suppress_context__ else error.__context__)


def _as_dict(value: Normalized) -> dict[str, Normalized]:
    return value if isinstance(value, dict) else {}
