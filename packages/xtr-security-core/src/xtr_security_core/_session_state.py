"""Reading the fields of a state a session kept, refusing one of the wrong type.

A session is kept outside the process, so what comes back from it is data, and
only data of the shape a ``from_session`` hook expects may become a token or a
user again. Each reader takes one field and answers it typed, or refuses the
whole state with :class:`~xtr_security_core.exception.InvalidArgumentError` —
which the code reading a session turns into "this is not a token", never into
a failed request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "boolean_field",
    "mapping_field",
    "optional_boolean_field",
    "optional_mapping_field",
    "optional_string_field",
    "string_field",
    "strings_field",
]


def string_field(state: Mapping[str, object], name: str) -> str:
    """Return the non-empty string under ``name``.

    Raises:
        InvalidArgumentError: When the field is missing, empty or not a string.
    """
    value = state.get(name)
    if not isinstance(value, str) or value == "":
        raise InvalidArgumentError(f'The session state\'s "{name}" must be a non-empty string.')
    return value


def optional_string_field(state: Mapping[str, object], name: str) -> str | None:
    """Return the string under ``name``, or ``None`` when the field holds none.

    Raises:
        InvalidArgumentError: When the field holds something else than a string.
    """
    value = state.get(name)
    if value is not None and not isinstance(value, str):
        raise InvalidArgumentError(f'The session state\'s "{name}" must be a string or null.')
    return value


def boolean_field(state: Mapping[str, object], name: str) -> bool:
    """Return the boolean under ``name``.

    Raises:
        InvalidArgumentError: When the field is missing or not a boolean.
    """
    value = state.get(name)
    if not isinstance(value, bool):
        raise InvalidArgumentError(f'The session state\'s "{name}" must be a boolean.')
    return value


def optional_boolean_field(state: Mapping[str, object], name: str) -> bool | None:
    """Return the boolean under ``name``, or ``None`` when the field holds none.

    Raises:
        InvalidArgumentError: When the field holds something else than a boolean.
    """
    value = state.get(name)
    if value is not None and not isinstance(value, bool):
        raise InvalidArgumentError(f'The session state\'s "{name}" must be a boolean or null.')
    return value


def strings_field(state: Mapping[str, object], name: str) -> list[str]:
    """Return the list of strings under ``name``, as a list of its own.

    Raises:
        InvalidArgumentError: When the field is missing, not a list, or holds
            anything but strings.
    """
    value = state.get(name)
    if not isinstance(value, list):
        raise InvalidArgumentError(f'The session state\'s "{name}" must be a list of strings.')
    items = cast("list[object]", value)
    strings = [item for item in items if isinstance(item, str)]
    if len(strings) != len(items):
        raise InvalidArgumentError(f'The session state\'s "{name}" must be a list of strings.')
    return strings


def mapping_field(state: Mapping[str, object], name: str) -> dict[str, object]:
    """Return the object under ``name``, as a dictionary of its own.

    Raises:
        InvalidArgumentError: When the field is missing, not an object, or
            keyed by anything but strings.
    """
    value = state.get(name)
    if not isinstance(value, dict):
        raise InvalidArgumentError(f'The session state\'s "{name}" must be an object.')
    return _keyed_by_strings(cast("dict[object, object]", value), name)


def optional_mapping_field(state: Mapping[str, object], name: str) -> dict[str, object] | None:
    """Return the object under ``name``, or ``None`` when the field holds none.

    Raises:
        InvalidArgumentError: When the field holds something else than an
            object keyed by strings.
    """
    value = state.get(name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise InvalidArgumentError(f'The session state\'s "{name}" must be an object or null.')
    return _keyed_by_strings(cast("dict[object, object]", value), name)


def _keyed_by_strings(entries: dict[object, object], name: str) -> dict[str, object]:
    """Return ``entries`` copied, refusing a key that is not a string."""
    mapping = {key: item for key, item in entries.items() if isinstance(key, str)}
    if len(mapping) != len(entries):
        raise InvalidArgumentError(f'The session state\'s "{name}" must be keyed by strings.')
    return mapping
