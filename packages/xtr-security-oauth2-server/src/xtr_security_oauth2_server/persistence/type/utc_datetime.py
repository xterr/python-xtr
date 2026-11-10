"""The column an instant is stored in, in UTC, whatever the database can keep."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator
from typing_extensions import override
from xtr_clock import DatePoint
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from sqlalchemy import Dialect

__all__ = ["UtcDateTime"]


@final
class UtcDateTime(TypeDecorator[datetime]):
    """Stores an instant in UTC, and reads it back knowing that is what it is.

    Everything here is compared against a clock that always reports a
    timezone-aware instant, and comparing one of those with a naive instant
    raises rather than guessing. Databases do not agree on time zones —
    PostgreSQL keeps one, SQLite and MySQL drop it — so the zone is settled
    here instead: what goes in is moved to UTC and handed to the driver as
    exactly a plain naive ``datetime``, and what comes back is handed over as
    UTC. Every backend then behaves the same, and a row read by something that
    is not this package reads as UTC too.

    Exactly a plain ``datetime``, because the drivers do not agree on anything
    else either: asyncpg refuses an aware value for a column without a zone,
    psycopg and MySQL convert the offset they are handed — storing another
    instant — and PyMySQL does not recognise a ``datetime`` subclass, so a
    clock's ``DatePoint`` would reach it as text, offset and all.

    A naive instant is refused rather than assumed to be UTC: it would be the
    machine's local time about half the time, and a credential whose expiry is
    hours out either keeps working after it should not or stops working before
    it should.
    """

    impl = DateTime
    cache_ok = True

    @override
    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Move ``value`` to UTC and drop the zone, which is now implied.

        The clock hands over a ``DatePoint``, which ``replace(tzinfo=None)``
        cannot make naive; its own naive UTC reading is what the driver gets.

        Raises:
            InvalidArgumentError: When ``value`` carries no time zone.
        """
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            raise InvalidArgumentError(
                f"The instant {value.isoformat()} carries no time zone, so storing it would "
                "guess at one; read it off a clock, which always reports the zone.",
            )

        return DatePoint.from_datetime(value).to_naive_utc()

    @override
    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Hand back what was stored as the UTC instant it is.

        A plain aware ``datetime`` in UTC, deliberately not a ``DatePoint``:
        the entities and grants compare instants, and every reader of the row
        gets the standard library's type.
        """
        del dialect
        if value is None:
            return None

        return value.replace(tzinfo=UTC)
