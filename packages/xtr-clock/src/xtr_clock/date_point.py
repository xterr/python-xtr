"""An instant that stays aware, and stays a ``DatePoint``.

``DatePoint`` is a :class:`~datetime.datetime`, so everything already
written against one keeps working: comparison, subtraction, formatting,
``strftime``, ``isoformat``, sorting, a database driver. It adds two
guarantees the standard library leaves to the caller.

**It is always timezone-aware.** A naive reading is taken as local time, the
same way the standard library reads one when it converts. There is therefore
no such thing as a ``DatePoint`` whose offset is unknown, which is what makes
comparing two of them always meaningful.

**It stays a ``DatePoint``.** ``replace``, ``astimezone``, adding a
:class:`~datetime.timedelta`, ``fromisoformat``, ``strptime`` — each answers
with a ``DatePoint``, so the type survives a chain of operations and the
guarantee above survives with it.

``now()`` reads the clock in force rather than the operating system, so a
frozen clock in a test reaches code that never heard of this library's
interfaces.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Self, TypeVar

from .modifier import apply_modifier
from .timezone import local_timezone, resolve_timezone

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import tzinfo
    from typing import SupportsIndex

__all__ = ["DatePoint"]

_DatePointT = TypeVar("_DatePointT", bound="DatePoint")


class DatePoint(datetime):
    """A timezone-aware instant that survives every operation as itself."""

    __slots__: ClassVar[tuple[str, ...]] = ()

    def __new__(
        cls,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
        tzinfo: tzinfo | None = None,
        *,
        fold: int = 0,
    ) -> Self:
        """Build an instant, attaching the local zone when none is given.

        Args:
            year: The year.
            month: The month, 1 to 12.
            day: The day of the month.
            hour: The hour, 0 to 23.
            minute: The minute.
            second: The second.
            microsecond: The microsecond.
            tzinfo: The zone these fields are read in. ``None`` means local,
                which is the reading the standard library gives a naive
                datetime whenever it has to pick one.
            fold: Which of two identical wall clocks is meant, when a
                daylight saving change produced the same one twice.
        """
        return super().__new__(
            cls,
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            tzinfo if tzinfo is not None else local_timezone(),
            fold=fold,
        )

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> Self:
        """Return the current instant, read from the clock in force.

        This is the one method that departs from
        :meth:`datetime.datetime.now`: it asks
        :meth:`~xtr_clock.clock.Clock.get` rather than the operating system,
        so freezing the clock in a test reaches code that calls
        ``DatePoint.now()`` without having been handed a clock.

        Args:
            tz: The zone to read the instant in. ``None`` keeps whichever
                zone the clock answers in.
        """
        from .clock import Clock  # noqa: PLC0415 — deferred: Clock answers in DatePoint

        moment = Clock.get().now()

        return cls.from_datetime(moment if tz is None else moment.astimezone(tz))

    @classmethod
    def parse(
        cls,
        spec: str,
        timezone: str | tzinfo | None = None,
        *,
        reference: datetime | None = None,
    ) -> Self:
        """Return the instant ``spec`` describes.

        ``spec`` is read by the grammar documented on
        :mod:`xtr_clock.modifier`: an offset like ``'+1 day'``, a keyword
        like ``'tomorrow'``, an ISO-8601 datetime, a timezone name, or any
        of them with a zone trailing.

        Args:
            spec: The modifier to read.
            timezone: The zone to read the reference in before applying
                ``spec``. A zone named inside ``spec`` wins over this one.
            reference: The instant ``spec`` is relative to. Defaults to
                whatever the clock in force says now is.

        Returns:
            The instant described.

        Raises:
            InvalidModifierError: When the grammar cannot read ``spec``.
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        if reference is None:
            from .clock import Clock  # noqa: PLC0415 — deferred: Clock answers in DatePoint

            reference = Clock.get().now()

        base = cls.from_datetime(reference)
        if timezone is not None:
            base = base.with_timezone(timezone)

        return cls.from_datetime(apply_modifier(base, spec))

    @classmethod
    def from_datetime(cls, value: datetime) -> Self:
        """Return ``value`` as a ``DatePoint``.

        A ``DatePoint`` is returned unchanged, so adopting one that already
        is costs nothing. A naive datetime is read as local time.

        Args:
            value: The datetime to adopt.
        """
        if isinstance(value, cls):
            return value

        return cls(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
            value.tzinfo,
            fold=value.fold,
        )

    def modify(self, modifier: str) -> Self:
        """Return the instant ``modifier`` describes, relative to this one.

        Args:
            modifier: A modifier the grammar on :mod:`xtr_clock.modifier`
                can read.

        Returns:
            A new instant; this one is unchanged.

        Raises:
            InvalidModifierError: When the grammar cannot read ``modifier``.
        """
        return type(self).from_datetime(apply_modifier(self, modifier))

    def with_timezone(self, timezone: str | tzinfo) -> Self:
        """Return this same instant, read in another zone.

        The moment does not move — only the wall clock showing it does.

        Args:
            timezone: A name, an offset, or a resolved zone.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        return self.astimezone(resolve_timezone(timezone))

    def __reduce_ex__(
        self, protocol: SupportsIndex
    ) -> tuple[Callable[..., Self], tuple[object, ...]]:
        """Pickle and copy through :meth:`__reduce__`, which pins the fields.

        The inherited implementation answers pickle directly and never
        consults ``__reduce__``, so overriding only that one would leave both
        pickling and copying on the packed path this class does not read.
        """
        return self.__reduce__()

    def __reduce__(self) -> tuple[Callable[..., Self], tuple[object, ...]]:
        """Pickle by field rather than by packed state.

        The inherited form hands the constructor a packed byte string this
        class does not read. Rebuilding from the fields it does read keeps
        unpickling on the same path as every other way of making an instant,
        so a restored one carries the same guarantees.
        """
        return (
            _rebuild,
            (
                type(self),
                self.year,
                self.month,
                self.day,
                self.hour,
                self.minute,
                self.second,
                self.microsecond,
                self.tzinfo,
                self.fold,
            ),
        )


def _rebuild(
    cls: type[_DatePointT],
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    microsecond: int,
    tzinfo: tzinfo | None,
    fold: int,
) -> _DatePointT:
    """Rebuild a pickled instant. Named at module level so pickle can find it."""
    return cls(year, month, day, hour, minute, second, microsecond, tzinfo, fold=fold)
