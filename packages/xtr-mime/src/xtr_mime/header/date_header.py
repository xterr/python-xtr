"""A header holding a date, such as Date."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, final

from typing_extensions import override

from .abstract_header import AbstractHeader

__all__ = ["DateHeader"]


@final
class DateHeader(AbstractHeader):
    """A header whose body is a date, written in RFC 5322 form at the date's own UTC offset.

    The offset is kept, not converted to UTC: it tells the reader the sender's local time.
    A date without one is written ``-0000``, which RFC 5322 reads as "offset unknown".
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_date_time",)

    def __init__(self, name: str, date_time: datetime) -> None:
        """Keep ``name`` and ``date_time``.

        Raises:
            RfcComplianceError: ``name`` is not a header name.
        """
        super().__init__(name)
        self._date_time = date_time

    @override
    def set_body(self, body: object) -> None:
        """Replace the date.

        Raises:
            InvalidArgumentError: ``body`` is not a :class:`~datetime.datetime`.
        """
        if not isinstance(body, datetime):
            self._refuse_body("a datetime", body)
        self.set_date_time(body)

    @override
    def get_body(self) -> datetime:
        """Return the date."""
        return self._date_time

    def get_date_time(self) -> datetime:
        """Return the date."""
        return self._date_time

    def set_date_time(self, date_time: datetime) -> None:
        """Replace the date."""
        self._date_time = date_time

    @override
    def _engine_value(self) -> datetime:
        return self._date_time
