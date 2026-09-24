"""Stamps records with a fixed set of tags, for picking them out later."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .processor_interface import ProcessorInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.log_record import LogRecord

__all__ = ["TagProcessor"]


@final
class TagProcessor(ProcessorInterface):
    """Adds ``extra["tags"]`` — labels shared by every record it processes.

    Attach one to a channel to mark where its records came from — ``"billing"``,
    ``"deploy"`` — so they can be filtered downstream without parsing the
    message. The tags may be changed while the application is being wired.
    """

    __slots__ = ("_tags",)

    def __init__(self, tags: Sequence[str] = ()) -> None:
        """Start with ``tags``."""
        self._tags: tuple[str, ...] = tuple(tags)

    def add_tags(self, *tags: str) -> None:
        """Add ``tags`` to those already set."""
        self._tags = (*self._tags, *tags)

    def set_tags(self, tags: Sequence[str]) -> None:
        """Replace the tags with ``tags``."""
        self._tags = tuple(tags)

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record`` with the tags in ``extra``."""
        return record.with_extra({"tags": list(self._tags)})
