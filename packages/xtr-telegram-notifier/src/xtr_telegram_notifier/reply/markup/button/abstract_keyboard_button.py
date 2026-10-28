"""The base of every keyboard button."""

from __future__ import annotations

import copy
from abc import ABC

__all__ = ["AbstractKeyboardButton"]


class AbstractKeyboardButton(ABC):  # noqa: B024 -- abstract by role: only its subclasses mean anything to the bot API
    """One button of a keyboard, rendered into the keyboard's rows.

    A subclass fills :attr:`_options` with the bot API's fields.
    """

    def __init__(self) -> None:
        """Start with no field set."""
        self._options: dict[str, object] = {}

    def to_array(self) -> dict[str, object]:
        """Render the button as the bot API reads it — a copy, so it stays as it was."""
        return copy.deepcopy(self._options)
