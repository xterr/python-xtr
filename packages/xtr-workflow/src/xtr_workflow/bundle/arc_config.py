"""Configuration of one arc of a configured transition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_workflow.exception import InvalidArgumentError

from ._place_name import place_name

if TYPE_CHECKING:
    from enum import Enum

__all__ = ["ArcConfig"]


@final
@dataclass(frozen=True, slots=True)
class ArcConfig:
    """How many tokens a configured transition moves through one place.

    ```python
    TransitionConfig("merge", froms=(ArcConfig("done", 2), "extra"), tos="archived")
    ```

    Attributes:
        place: The name of the place; a member of a string enum given here
            is read as its value.
        weight: The number of tokens; at least 1.
    """

    place: str
    weight: int = 1

    if TYPE_CHECKING:
        # The place may be given as an enum member, read as its value by
        # ``__post_init__``; the attribute always holds the name.
        def __init__(self, place: str | Enum, weight: int = 1) -> None:
            """Name the place, and weigh it."""

    def __post_init__(self) -> None:
        """Read the place's name, and refuse an arc that leads nowhere or moves no token.

        Raises:
            InvalidArgumentError: If the place is empty or a member of an enum
                not valued with strings, or the weight is below 1.
        """
        object.__setattr__(self, "place", place_name(self.place))
        if not self.place:
            raise InvalidArgumentError(
                'The place of an arc cannot contain an empty value, but got "".'
            )
        if self.weight < 1:
            raise InvalidArgumentError(
                f"The value {self.weight} is too small for the weight of an arc. Should be "
                "greater than or equal to 1."
            )
