"""An add-on this tool does not know, or one the chosen template cannot take."""

from __future__ import annotations

from typing import final

from .cli_error import CliError

__all__ = ["UnknownAddOnError"]


@final
class UnknownAddOnError(CliError):
    """``--with`` names an add-on, or a variant of one, that cannot be added.

    Attributes:
        add_on: The add-on as it was spelled.
        reason: Why it cannot be added, naming what could be chosen instead.
    """

    add_on: str
    reason: str

    def __init__(self, add_on: str, reason: str) -> None:
        """Record the add-on and why it was refused."""
        self.add_on = add_on
        self.reason = reason
        super().__init__(f"cannot add {add_on!r}: {reason}")
