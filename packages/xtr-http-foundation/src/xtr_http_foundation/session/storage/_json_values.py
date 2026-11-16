"""The rule every session storage keeps its values by: what JSON gives back as it was given."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from xtr_http_foundation.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["decoded", "encoded"]


def encoded(data: Mapping[str, object]) -> str:
    """Return ``data`` as the JSON an entry stores, or refuse what cannot round-trip.

    A value that would come back as something else than it went in — a
    tuple that would return a list, a key that would return a string — is
    not a value the session can rely on reading again, so it is refused
    here, where the caller can still hear it.

    Raises:
        InvalidArgumentError: When ``data`` holds a value JSON cannot give
            back as it was given.
    """
    values = dict(data)

    try:
        text = json.dumps(values, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise InvalidArgumentError(
            "A session value must round-trip through JSON — a string, a number, a boolean, "
            f"None, a list or a dictionary of them — and one of them does not: {error}.",
        ) from error

    if decoded(text) != values:
        raise InvalidArgumentError(
            "A session value must round-trip through JSON — a string, a number, a boolean, "
            "None, a list or a dictionary of them; something in this session is not.",
        )

    return text


def decoded(text: str) -> dict[str, object] | None:
    """Return the attributes ``text`` encodes, or ``None`` when it is no JSON object."""
    try:
        value = cast("object", json.loads(text))
    except ValueError:
        return None
    if not isinstance(value, dict):
        return None
    # A decoded JSON object is keyed by strings; the cast says so once
    # rather than at every lookup the caller makes.
    return cast("dict[str, object]", value)
