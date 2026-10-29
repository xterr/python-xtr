"""Data was read to the end, and some of its values did not fit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .invalid_argument_error import InvalidArgumentError
from .unexpected_value_error import UnexpectedValueError

if TYPE_CHECKING:
    from .not_normalizable_value_error import NotNormalizableValueError

__all__ = ["PartialDenormalizationError"]


class PartialDenormalizationError(UnexpectedValueError):
    """Data was read to the end, and some of its values did not fit their types.

    Raised in place of the first error when the reading side is asked to collect
    every error, so a form or an API request can be answered with everything
    that is wrong at once rather than one field per attempt.

    The message lists the errors, each by its path and types. The data is never
    part of it: it is what someone sent, and may hold a secret.

    Attributes:
        data: What was being denormalized — for the code handling the error to
            use, never for the message.
        errors: One error for each value that did not fit, each naming its path.
    """

    data: object
    errors: tuple[NotNormalizableValueError, ...]

    def __init__(self, data: object, errors: tuple[NotNormalizableValueError, ...]) -> None:
        """Record the data that was read and every error found in it.

        Raises:
            InvalidArgumentError: If ``errors`` is empty. Nothing was found, so there
                is nothing to report; raising this error anyway is a mistake in the
                code that raises it.
        """
        if not errors:
            raise InvalidArgumentError(
                "PartialDenormalizationError needs at least one error to report"
            )
        self.data = data
        self.errors = errors
        count = "1 error" if len(errors) == 1 else f"{len(errors)} errors"
        found = "; ".join(str(error) for error in errors)
        super().__init__(f"the data could not be denormalized ({count}): {found}")
