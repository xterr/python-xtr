"""How many tokens a transition moves through one place."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from .exception import InvalidArgumentError

__all__ = ["Arc"]


@final
@dataclass(frozen=True, slots=True)
class Arc:
    """How many tokens a transition takes from one place, or puts in it.

    On the way in, an arc's weight is both what the place must hold for the
    transition to be enabled and what applying it takes away; on the way out,
    it is what applying it puts in. A transition given a bare place name
    weighs it 1, which is all a state machine ever uses.

    Attributes:
        place: The name of the place; never empty.
        weight: The number of tokens; at least 1.
    """

    place: str
    weight: int = 1

    def __post_init__(self) -> None:
        """Refuse an arc that could not move a token, or that leads nowhere.

        Raises:
            InvalidArgumentError: If ``weight`` is below 1 or ``place`` is empty.
        """
        if self.weight < 1:
            raise InvalidArgumentError(f"The weight must be greater than 0, {self.weight} given.")
        if not self.place:
            raise InvalidArgumentError("The place name cannot be empty.")
