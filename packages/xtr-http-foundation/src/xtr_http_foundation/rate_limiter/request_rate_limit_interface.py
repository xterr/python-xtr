"""The state of a limit over requests, as one consumption left it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["RequestRateLimitInterface"]


@runtime_checkable
class RequestRateLimitInterface(Protocol):
    """The state of a limit over requests, as one consumption left it.

    A request limiter does not keep the count itself — it reads the limiters
    it is built from, and answers with the state the strictest of them was
    left in. This is the shape it reads that state through, so a limiter
    answers in its own result type rather than one this library prescribes:
    whatever carries these members serves, and the members are named as the
    counting packages name them, so theirs do.

    Two instants are told apart. :attr:`retry_after` is when the tokens this
    caller asked for become available; :attr:`reset_at` is when the limiter
    is back to holding every token — ``None`` for a limit that has no such
    moment.
    """

    def is_accepted(self) -> bool:
        """Tell whether the tokens asked for were granted."""
        ...

    @property
    def remaining_tokens(self) -> int:
        """How many tokens are left."""
        ...

    @property
    def retry_after(self) -> datetime:
        """When the tokens asked for become available."""
        ...

    @property
    def limit(self) -> int:
        """How many tokens the limiter holds when full."""
        ...

    @property
    def reset_at(self) -> datetime | None:
        """When the limiter holds every token again; ``None`` when it has no such moment."""
        ...
