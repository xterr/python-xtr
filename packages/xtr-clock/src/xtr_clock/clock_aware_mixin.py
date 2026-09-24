"""A mixin for a class that needs to know what time it is."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from .clock import Clock

if TYPE_CHECKING:
    from .clock_interface import ClockInterface
    from .date_point import DatePoint

__all__ = ["ClockAwareMixin"]


class ClockAwareMixin:
    """Gives a class a clock it can be handed, and a default until it is.

    Taking a :class:`~xtr_clock.clock_interface.ClockInterface` as a
    constructor argument is still the clearest thing to do. This is for the
    case where you cannot: a class whose constructor is already spoken for
    by a framework, or a long-lived one you are making testable without
    rewriting every place that builds it.

    It defines no ``__init__``, so it composes with any class — including a
    dataclass — and reads the clock in force until :meth:`set_clock` says
    otherwise.

    ```python
    class TokenIssuer(ClockAwareMixin):
        def issue(self) -> Token:
            return Token(expires_at=self.now().modify("+1 hour"))


    issuer = TokenIssuer()
    issuer.set_clock(MockClock("2024-04-09 12:00:00"))
    ```
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_clock",)

    _clock: ClockInterface

    def set_clock(self, clock: ClockInterface) -> None:
        """Read time from ``clock`` from now on."""
        self._clock = clock

    @property
    def clock(self) -> ClockInterface:
        """The clock this object reads: the one it was given, or the one in force."""
        try:
            return self._clock
        except AttributeError:
            return Clock.get()

    def now(self) -> DatePoint:
        """Return the current instant, according to this object's clock."""
        return self.clock.now()
