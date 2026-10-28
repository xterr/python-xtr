"""The name of a place configuration names by a string or by an enum member."""

from __future__ import annotations

from enum import Enum
from typing import cast

from xtr_workflow.decorator._workflow_name import class_name
from xtr_workflow.exception import InvalidArgumentError

__all__ = ["place_name"]


def place_name(place: str | Enum) -> str:
    """Return the name ``place`` stands for: the string itself, or the member's value.

    A member of a string enum is a string already, but its value is taken all
    the same: the definition, the markings and the dumpers then hold plain
    strings, whichever way the configuration named the place.

    Raises:
        InvalidArgumentError: If ``place`` is a member of an enum not valued
            with strings.
    """
    if not isinstance(place, Enum):
        return place

    value = cast("object", place.value)
    if not isinstance(value, str):
        raise InvalidArgumentError(
            f'Only string-backed enums can be used as places, "{class_name(type(place))}" is not.'
        )

    return value
