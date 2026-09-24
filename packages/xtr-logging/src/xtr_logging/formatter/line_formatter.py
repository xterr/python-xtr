"""One line of text per record."""

from __future__ import annotations

import re
import traceback
from typing import TYPE_CHECKING, Final

import msgspec
from typing_extensions import override

from .formatter_interface import FormatterInterface
from .normalizer import Normalizer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.log_record import LogRecord

    from .normalizer import Normalized

__all__ = ["LineFormatter"]

_KEYED_TOKEN: Final = re.compile(r"%(context|extra)\.([^%]+)%")
_LEFTOVER_KEYED_TOKEN: Final = re.compile(r"%(?:context|extra)\.[^%]+%")
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

        def keyed(match: re.Match[str]) -> str:
            source = context if match.group(1) == "context" else extra
            key = match.group(2)
            if key not in source:
                return match.group(0)
            return self._stringify(source.pop(key))

        output = _KEYED_TOKEN.sub(keyed, self._format)
        if self._ignore_empty:
            for token, bag in (("%context%", context), ("%extra%", extra)):
                if not bag:
                    output = output.replace(f" {token}", "").replace(token, "")
        values: dict[str, str] = {
            "datetime": self._normalizer.format_datetime(record.datetime),
            "channel": record.channel,
            "level_name": record.level_name,
            "level": str(record.level.value),
            "message": self._stringify(record.message),
            "context": self._stringify_bag(context),
            "extra": self._stringify_bag(extra),
        }
        for token, value in values.items():
            output = output.replace(f"%{token}%", value)
        output = _LEFTOVER_KEYED_TOKEN.sub("", output)
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
        previous = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
        while previous is not None:
            text += f"\n[previous exception] [object] ({_describe(previous)})"
            previous = previous.__cause__ or (
                None if previous.__suppress_context__ else previous.__context__
            )
        if self.include_stacktraces and error.__traceback__ is not None:
            text += "\n[stacktrace]\n" + "".join(traceback.format_tb(error.__traceback__))
        return text


def _describe(error: BaseException) -> str:
    kind = type(error)
    name = (
        kind.__qualname__
        if kind.__module__ == "builtins"
        else f"{kind.__module__}.{kind.__qualname__}"
    )
    frames = traceback.extract_tb(error.__traceback__)
    origin = f" at {frames[-1].filename}:{frames[-1].lineno}" if frames else ""
    return f"{name}: {error}{origin}"


def _as_dict(value: Normalized) -> dict[str, Normalized]:
    return value if isinstance(value, dict) else {}
