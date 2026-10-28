"""The base of every element placed inside a Slack block."""

from __future__ import annotations

import copy
from abc import ABC

from typing_extensions import override

from .slack_block_element_interface import SlackBlockElementInterface

__all__ = ["AbstractSlackBlockElement"]


class AbstractSlackBlockElement(SlackBlockElementInterface, ABC):
    """An element whose fields a subclass fills in :attr:`_options`."""

    def __init__(self) -> None:
        """Start with no field set."""
        self._options: dict[str, object] = {}

    @override
    def to_array(self) -> dict[str, object]:
        """Render the element — a copy, so it stays as it was."""
        return copy.deepcopy(self._options)
