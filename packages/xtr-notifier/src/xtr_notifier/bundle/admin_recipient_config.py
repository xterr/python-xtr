"""One administrator of the application, as configured."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_notifier.exception import InvalidArgumentError

__all__ = ["AdminRecipientConfig"]


@final
@dataclass(frozen=True, slots=True)
class AdminRecipientConfig:
    """An administrator the application's own failures are reported to.

    Attributes:
        email: Where to write to them; required, so every administrator stays
            reachable once an email channel exists.
        phone: Their phone number, international form with no spaces, for the
            SMS channel; ``""`` when they have none.
    """

    email: str
    phone: str = ""

    def __post_init__(self) -> None:
        """Refuse an administrator with no email.

        Raises:
            InvalidArgumentError: If ``email`` is empty.
        """
        if not self.email:
            raise InvalidArgumentError("An admin recipient needs an email.")
