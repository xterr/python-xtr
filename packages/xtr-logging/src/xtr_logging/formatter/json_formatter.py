"""Every record as one JSON object."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import msgspec
from typing_extensions import override

from .formatter_interface import FormatterInterface
from .json_batch_mode import JsonBatchMode
from .normalizer import Normalizer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.log_record import Context, LogRecord

    from .normalizer import Normalized

__all__ = ["JsonFormatter"]


@final
class JsonFormatter(FormatterInterface):
    """Renders a record as a single JSON object, one per line by default.

    The object carries ``message``, ``context``, ``level`` (the numeric value),
    ``level_name``, ``channel``, ``datetime`` and ``extra``, in that order, so
    a log shipper can rely on the shape. Values are reduced to plain JSON by
    :class:`~xtr_logging.formatter.normalizer.Normalizer`, an exception becoming
    the structure it describes.

    A batch is either one JSON array or one object per line, per
    :class:`JsonBatchMode` — the latter being the newline-delimited JSON that
    log shippers ingest.
    """

    __slots__ = ("_append_newline", "_batch_mode", "_ignore_empty", "_normalizer")

    def __init__(
        self,
        batch_mode: JsonBatchMode = JsonBatchMode.JSON,
        *,
        append_newline: bool = True,
        ignore_empty_context_and_extra: bool = False,
        include_stacktraces: bool = False,
        date_format: str | None = None,
    ) -> None:
        """Configure the JSON.

        Args:
            batch_mode: Whether :meth:`format_batch` yields one array or one
                object per line.
            append_newline: End each formatted record with a newline, so a file
                handler writes one object per line.
            ignore_empty_context_and_extra: Leave ``context`` or ``extra`` out
                entirely when empty, rather than writing ``{}``.
            include_stacktraces: Give an exception its traceback.
            date_format: A :meth:`~datetime.datetime.strftime` format for the
                timestamp; ISO 8601 when omitted.
        """
        self._batch_mode: JsonBatchMode = batch_mode
        self._append_newline: bool = append_newline
        self._ignore_empty: bool = ignore_empty_context_and_extra
        self._normalizer: Normalizer = Normalizer(
            date_format, include_stacktraces=include_stacktraces
        )

    @override
    def format(self, record: LogRecord, /) -> str:
        """Render ``record`` as one JSON object."""
        encoded = msgspec.json.encode(self._to_dict(record)).decode()
        return f"{encoded}\n" if self._append_newline else encoded

    @override
    def format_batch(self, records: Sequence[LogRecord], /) -> str:
        """Render ``records`` as one JSON array, or one object per line."""
        if self._batch_mode is JsonBatchMode.NEWLINES:
            return "\n".join(
                msgspec.json.encode(self._to_dict(record)).decode() for record in records
            )
        return msgspec.json.encode([self._to_dict(record) for record in records]).decode()

    def _to_dict(self, record: LogRecord) -> dict[str, Normalized]:
        data: dict[str, Normalized] = {"message": record.message}
        context = self._bag(record.context)
        if context is not None:
            data["context"] = context
        data["level"] = record.level.value
        data["level_name"] = record.level_name
        data["channel"] = record.channel
        data["datetime"] = self._normalizer.format_datetime(record.datetime)
        extra = self._bag(record.extra)
        if extra is not None:
            data["extra"] = extra
        return data

    def _bag(self, values: Context) -> Normalized | None:
        if values:
            return self._normalizer.normalize(values)
        return None if self._ignore_empty else {}
