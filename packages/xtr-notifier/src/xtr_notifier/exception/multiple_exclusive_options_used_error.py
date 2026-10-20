"""Options a provider accepts only one of, used together."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["MultipleExclusiveOptionsUsedError"]


class MultipleExclusiveOptionsUsedError(InvalidArgumentError):
    """Options that each pick what a message is — a photo, a location — were set together.

    Attributes:
        used_exclusive_options: The exclusive options that were set.
        exclusive_options: Every option only one of which may be set.
    """

    used_exclusive_options: tuple[str, ...]
    exclusive_options: tuple[str, ...]

    def __init__(
        self, used_exclusive_options: Sequence[str], exclusive_options: Sequence[str]
    ) -> None:
        """Name the clashing options and the set they belong to.

        Args:
            used_exclusive_options: The exclusive options that were set.
            exclusive_options: Every option only one of which may be set.
        """
        self.used_exclusive_options = tuple(used_exclusive_options)
        self.exclusive_options = tuple(exclusive_options)
        used = '", "'.join(self.used_exclusive_options)
        allowed = '", "'.join(self.exclusive_options)
        super().__init__(
            f'Multiple exclusive options have been used "{used}". '
            f'Only one of "{allowed}" can be used.'
        )
