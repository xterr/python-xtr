"""An enum whose members stand for places, each valued with the place's name.

A plain enum, not a string one: ``str()`` of a member is not its value, so a
store that forgets to read the value shows it.
"""

from __future__ import annotations

from enum import Enum


class PlaceEnum(Enum):
    FOO = "foo"
    BAR = "bar"
