"""Data carried attributes the type it was read into does not declare."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .not_normalizable_value_error import NotNormalizableValueError

__all__ = ["ExtraAttributesError"]


class ExtraAttributesError(NotNormalizableValueError):
    """Data for an object carried attributes its type does not declare.

    Raised when the reading side is set to refuse what it does not know rather
    than drop it — for data from a client that should hear about a misspelled
    field instead of having it silently ignored. It is one more value that did
    not fit, so it is collected with the others when every error is wanted.

    The message names the attributes, quoted as the path is, and leaves out
    what they held.

    Attributes:
        extra_attributes: The names of the attributes the type does not declare.
    """

    extra_attributes: tuple[str, ...]

    def __init__(
        self,
        extra_attributes: tuple[str, ...],
        *,
        path: str | None = None,
        expected_types: tuple[str, ...] = (),
        current_type: str | None = None,
        error_type: str | None = None,
    ) -> None:
        """Record the attributes the type does not declare, and where the data had them.

        Raises:
            InvalidArgumentError: If ``extra_attributes`` is empty. No attribute is
                extra, so there is nothing to refuse; raising this error anyway is a
                mistake in the code that raises it.
        """
        if not extra_attributes:
            raise InvalidArgumentError("ExtraAttributesError needs at least one extra attribute")
        self.extra_attributes = extra_attributes
        names = ", ".join(repr(name) for name in extra_attributes)
        super().__init__(
            f"extra attributes are not allowed: {names}",
            path=path,
            expected_types=expected_types,
            current_type=current_type,
            error_type=error_type,
        )
