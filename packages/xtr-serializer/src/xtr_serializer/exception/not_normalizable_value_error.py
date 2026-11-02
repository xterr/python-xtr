"""A value could not be turned into plain data, or plain data into the type asked for."""

from __future__ import annotations

from .unexpected_value_error import UnexpectedValueError

__all__ = ["NotNormalizableValueError"]


class NotNormalizableValueError(UnexpectedValueError):
    """A value cannot be turned into plain data, or plain data into the type asked for.

    Raised on both sides of the conversion: writing a value that has no exact
    plain form, or reading data that does not fit the declared type — a string
    where a number belongs, a required field missing. What is read mostly comes
    from someone else and may hold a password or a token, so the message is put
    together from the attributes below and nothing else: where the value sits
    and which types were involved, never the value. The path and the type names
    are quoted, so a key taken from the data cannot break the message across lines.

    Attributes:
        message: What is wrong with the value, in words that do not quote it.
        path: Where the value sits in what was being converted, such as
            ``"items[0].price"``; ``None`` for the value as a whole.
        expected_types: The names of the types the value could have had.
        current_type: The name of the type it had, when known.
        error_type: A short code for the kind of problem, such as
            ``"missing"``, for a program to act on; the message leaves it out.
    """

    message: str
    path: str | None
    expected_types: tuple[str, ...]
    current_type: str | None
    error_type: str | None

    def __init__(
        self,
        message: str,
        *,
        path: str | None = None,
        expected_types: tuple[str, ...] = (),
        current_type: str | None = None,
        error_type: str | None = None,
    ) -> None:
        """Record what is wrong with the value and where, without the value itself."""
        self.message = message
        self.path = path
        self.expected_types = expected_types
        self.current_type = current_type
        self.error_type = error_type
        location = f"at {path!r}: " if path else ""
        types = (
            [f"expected {' | '.join(repr(name) for name in expected_types)}"]
            if expected_types
            else []
        )
        if current_type:
            types.append(f"got {current_type!r}")
        detail = f" ({', '.join(types)})" if types else ""
        super().__init__(f"{location}{message}{detail}")
