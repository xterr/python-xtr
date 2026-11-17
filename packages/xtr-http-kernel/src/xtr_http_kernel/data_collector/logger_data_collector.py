"""Every log record the request made."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_logging_contracts import Level

from ._masking import MASK, is_sensitive_field
from .clone_var import clone_var

if TYPE_CHECKING:
    from xtr_logging import DebugHandler

    from .profiled_request import ProfiledRequest

__all__ = ["LoggerDataCollector"]

_NAME: Final = "logger"


@final
class LoggerDataCollector:
    """Keeps the records the request's unit of work logged, read off a debug handler.

    Read once everything has been sent, so what was logged while the body
    streamed is there too: each record's time, channel, level, message and
    context, and the counts a toolbar shows. A context entry named like a
    credential — a password, a secret, a token — is kept as ``******``, as
    the request's own fields are.
    """

    __slots__ = ("_handler",)

    def __init__(self, handler: DebugHandler) -> None:
        """Read the records ``handler`` keeps for the open unit of work."""
        self._handler = handler

    @property
    def name(self) -> str:
        """``"logger"``."""
        return _NAME

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the counts so far; the records follow once the response has left."""
        del profiled
        return self._read()

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return every record of the request."""
        del data, profiled
        return self._read()

    def _read(self) -> dict[str, object]:
        records = self._handler.get_logs()
        return {
            "records": [
                {
                    "time": record.datetime.isoformat(),
                    "channel": record.channel,
                    "level": record.level.name,
                    "priority": int(record.level),
                    "message": record.message,
                    "context": {
                        str(name): (
                            clone_var(MASK)
                            if is_sensitive_field(str(name))
                            else clone_var(value, max_depth=3)
                        )
                        for name, value in record.context.items()
                    },
                }
                for record in records
            ],
            "error_count": sum(1 for record in records if record.level >= Level.ERROR),
            "warning_count": sum(
                1 for record in records if Level.WARNING <= record.level < Level.ERROR
            ),
        }
