"""The envelope every email is sent with, whatever its headers say."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import final

from xtr_mailer._error_text import shown
from xtr_mailer.exception import InvalidArgumentError

__all__ = ["EnvelopeConfig"]


@final
@dataclass(frozen=True, slots=True)
class EnvelopeConfig:
    """The sender and recipients every email is delivered for, in place of its own.

    Buildable with no arguments: then every email keeps the envelope its headers give.

    Attributes:
        sender: The envelope sender of every email — where bounces go; ``None`` keeps each
            email's own. ``Name <address>`` is read as such.
        recipients: The only recipients every email is delivered to — on a staging server,
            say; empty keeps each email's own.
        allowed_recipients: Regular expressions in Python syntax, each matched against a whole
            recipient address; an email's own recipient one matches is delivered to as well as
            ``recipients``.
    """

    sender: str | None = None
    recipients: Sequence[str] = ()
    allowed_recipients: Sequence[str] = ()

    def __post_init__(self) -> None:
        """Refuse a list given as one string, and a pattern that does not compile.

        Raises:
            InvalidArgumentError: ``recipients`` or ``allowed_recipients`` is one string, or an
                allowed pattern is not a valid regular expression.
        """
        if isinstance(self.recipients, str):
            raise InvalidArgumentError(
                'The envelope "recipients" option must be a list of addresses, not one string.'
            )
        if isinstance(self.allowed_recipients, str):
            raise InvalidArgumentError(
                'The envelope "allowed_recipients" option must be a list of patterns, not one '
                "string."
            )
        for pattern in self.allowed_recipients:
            try:
                _ = re.compile(pattern)
            except re.error:
                raise InvalidArgumentError(
                    f'The allowed recipient pattern "{shown(pattern)}" is not a valid regular '
                    "expression."
                ) from None

    def is_configured(self) -> bool:
        """Tell whether the envelope of every email is to be changed."""
        return self.sender is not None or bool(self.recipients)
