"""Why data could not be read into its type, as this package's error, without the data."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pydantic_core import from_json

from xtr_serializer._type_names import name_of
from xtr_serializer.exception import (
    NotNormalizableValueError,
    PartialDenormalizationError,
)

from ._validation_refusals import refusals_of

if TYPE_CHECKING:
    from pydantic_core import ErrorDetails

__all__ = ["read_refusal"]


def read_refusal(
    data: object, details: list[ErrorDetails], text: bytes | None, *, collect: bool
) -> NotNormalizableValueError | PartialDenormalizationError:
    """Give the error to raise for ``data`` that pydantic refused to read.

    ``details`` are pydantic's errors, ``text`` the JSON it read, or ``None`` when it read the
    object itself. Read as JSON, the data is located in the JSON pydantic read, never in the
    caller's object, whose code could run, or which a generator or a set cannot be indexed into.
    ``collect`` gives every refusal at once rather than the first.
    """
    refusals = (
        refusals_of(details, data if text is None else _parsed(text), plain=text is not None)
        if details
        else []
    )
    if not refusals:
        return NotNormalizableValueError(
            "the data holds a value that is not plain data, or is nested too deep",
            current_type=name_of(type(data)),
        )
    if collect:
        return PartialDenormalizationError(data, tuple(refusals))
    return refusals[0]


def _parsed(text: bytes) -> object:
    """Parse the JSON pydantic read, or give ``None`` when it is nested past what parsing takes.

    pydantic reports such JSON as invalid as a whole, at no path, so nothing is lost.
    """
    try:
        return cast("object", from_json(text))
    except ValueError:
        return None
