"""One named transport of the mailer configuration: its DSN, and the limiter capping it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from xtr_mailer.exception import InvalidArgumentError

__all__ = ["TransportConfig"]


@final
@dataclass(frozen=True, slots=True)
class TransportConfig:
    """A transport, built from its DSN when the first email is sent.

    Attributes:
        dsn: One DSN, or a ``failover(...)`` / ``roundrobin(...)`` group of them. It carries
            credentials, so pass it through ``env("...")``; it is never shown.
        rate_limiter: The name of the xtr-rate-limiter limiter each email through the
            transport takes a token from; ``None`` caps nothing.
    """

    dsn: str = field(repr=False)
    rate_limiter: str | None = None

    def __post_init__(self) -> None:
        """Refuse an empty DSN or limiter name.

        Raises:
            InvalidArgumentError: The DSN or the limiter name is empty.
        """
        # Compared, never tested for truth: an env() placeholder cannot be tested at build.
        if self.dsn == "":
            raise InvalidArgumentError("A transport's DSN cannot be empty.")
        if self.rate_limiter == "":
            raise InvalidArgumentError("A transport's rate limiter name cannot be empty.")
