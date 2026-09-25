"""One thing that was logged, as it travels through processors and handlers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from xtr_logging_contracts import EXCEPTION_KEY

if TYPE_CHECKING:
    import datetime as dt

    from xtr_logging_contracts import Context, Level

__all__ = ["LogRecord"]

_EMPTY: Final[Context] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class LogRecord:
    """One thing that was logged.

    Immutable, so a record handed to several handlers — or to a queue that
    writes it later — cannot be changed under any of them. A processor returns
    a new record instead: :meth:`with_extra` for the common case,
    :func:`dataclasses.replace` for anything else.

    ``context`` and ``extra`` are copied on the way in, so a caller mutating
    the dictionary it logged cannot rewrite history either.

    Attributes:
        datetime: When the record was made, timezone-aware.
        channel: The name of the logger that made it.
        level: How severe it is.
        message: What happened, possibly holding ``{placeholders}``.
        context: What the caller attached. An exception goes under
            :data:`~xtr_logging_contracts.context.EXCEPTION_KEY`.
        extra: What processors attached. Kept apart from ``context`` so a
            processor can never overwrite something the caller said.
    """

    datetime: dt.datetime
    channel: str
    level: Level
    message: str
    context: Context = _EMPTY
    extra: Context = _EMPTY

    def __post_init__(self) -> None:
        """Freeze private copies of ``context`` and ``extra``."""
        object.__setattr__(self, "context", _frozen(self.context))
        object.__setattr__(self, "extra", _frozen(self.extra))

    @property
    def level_name(self) -> str:
        """The level's name in upper case, as formatters print it."""
        return self.level.name

    @property
    def exception(self) -> BaseException | None:
        """The exception under the ``exception`` key, if there is one."""
        found = self.context.get(EXCEPTION_KEY)
        return found if isinstance(found, BaseException) else None

    def with_extra(self, values: Context) -> LogRecord:
        """Return a copy with ``values`` merged into ``extra``, winning on conflict."""
        return replace(self, extra={**self.extra, **values})


def _frozen(values: Context) -> Context:
    return MappingProxyType(dict(values)) if values else _EMPTY
