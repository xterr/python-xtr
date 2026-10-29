"""pydantic's validation errors, as this package's errors, without the values."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_serializer._loc_path import render_path
from xtr_serializer.exception import ExtraAttributesError, NotNormalizableValueError

if TYPE_CHECKING:
    from pydantic_core import ErrorDetails

__all__ = ["refusals_of"]


def refusals_of(details: list[ErrorDetails]) -> list[NotNormalizableValueError]:
    """Turn pydantic's errors into this package's, in pydantic's order, without the values.

    Each keeps pydantic's message, which describes the type rather than the value, its path and
    its error type, and the name of the type the value had. pydantic reports each field an object
    should not have on its own; they are reported as one error naming them all, where the first
    of them was, as a reader would want to hear about a misspelled object.
    """
    extras: dict[str | None, list[str]] = {}
    for detail in details:
        if detail["type"] == "extra_forbidden":
            extras.setdefault(render_path(detail["loc"][:-1]), []).append(str(detail["loc"][-1]))
    refusals: list[NotNormalizableValueError] = []
    for detail in details:
        if detail["type"] != "extra_forbidden":
            refusals.append(
                NotNormalizableValueError(
                    detail["msg"],
                    path=render_path(detail["loc"]),
                    current_type=type(cast("object", detail["input"])).__name__,
                    error_type=detail["type"],
                )
            )
            continue
        path = render_path(detail["loc"][:-1])
        if (names := extras.pop(path, None)) is not None:
            refusals.append(
                ExtraAttributesError(tuple(names), path=path, error_type="extra_forbidden")
            )
    return refusals
