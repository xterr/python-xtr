"""Plain data read back before it is handed out, so what would not come back equal is refused."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError
from pydantic_core import to_json

from xtr_serializer.exception import NotNormalizableValueError

from ._validation_refusals import refusals_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_serializer.normalized_value import NormalizedValue

__all__ = ["read_back_refusal"]


def read_back_refusal(
    value: object, written: NormalizedValue, read: Callable[[bytes], object]
) -> NotNormalizableValueError | None:
    """Say why ``written`` would not read back as ``value``, or ``None`` when it would.

    pydantic writes what it holds by the field's declared type, and where a field declares nothing
    — ``Any``, a bare ``list`` or ``dict`` — by what it finds: a set or a tuple as a list, a key
    that is not a string as one, a model as a mapping. It also writes what it cannot read: a
    decimal NaN as ``"NaN"``. None of that warns. Reading the data back with ``read`` and comparing
    finds all of it, whichever field it hides in.

    A refusal by reading says where, from pydantic's location. A value that reads back changed
    has no location: pydantic only says the two differ.
    """
    try:
        # Infinity written as itself, so that reading refuses it rather than seeing null.
        read_value = read(to_json(written, inf_nan_mode="constants"))
    except ValidationError as error:
        first = refusals_of(error.errors(include_url=False, include_context=False), written)[0]
        return NotNormalizableValueError(
            f"it would not read back: {first.message}",
            path=first.path,
            error_type=first.error_type,
        )
    if read_value == value:
        return None
    return NotNormalizableValueError(
        "it would read back changed: a field declaring no type holds a set, a tuple, an object or "
        "a key that is not a string; a datetime field holds a zone in an hour the clocks repeat, "
        "which ZonedDateTime keeps; or its type does not compare by value",
        current_type=type(value).__qualname__,
        error_type="not_exact",
    )
