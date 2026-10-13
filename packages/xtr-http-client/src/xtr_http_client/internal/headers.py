"""Headers as a client keeps them: whole lines, found by a lowered name."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Final

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.debug_type import debug_type

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

__all__ = ["normalize_headers", "should_buffer"]

_FORBIDDEN: Final = ("\r", "\n", "\0")
_WORTH_REREADING: Final = re.compile(
    r"^(?:text/|application/(?:.+\+)?(?:json|xml)$)",
    re.IGNORECASE,
)


def normalize_headers(
    headers: Mapping[str, str | Sequence[str]] | Sequence[str],
) -> dict[str, list[str]]:
    """Turn whatever a caller wrote into lines, keyed by the lowered name.

    A header is kept as the line it will be sent as — ``"Accept: */*"``, the
    name in the case the caller chose — and found under that name lowered,
    because that is the only way two spellings of one header can be told to be
    the same one. A name maps to the list of its lines, so a header sent twice
    stays twice.

    A name mapped to nothing at all is kept with no lines: the caller said
    something about that header, and that is enough to stop a default filling
    it in.

    Args:
        headers: Names mapped to one value or several, or whole
            ``"Name: value"`` lines.

    Returns:
        Lowered name to the lines it will be sent as.

    Raises:
        InvalidArgumentError: When a value cannot be written out as text, or
            carries a character that would end the line early and let the
            caller write a head of their own.
    """
    normalized: dict[str, list[str]] = {}

    for name, values in _entries(headers):
        lines: list[str] = []
        for value in values:
            line = f"{name}: {value}"
            if any(character in line for character in _FORBIDDEN):
                raise InvalidArgumentError(f'Invalid header: CR/LF/NUL found in "{line}".')
            lines.append(line)
        normalized[name.lower()] = lines

    return normalized


def should_buffer(headers: Mapping[str, Sequence[str]]) -> bool:
    """Tell whether a response of this kind is worth keeping once read.

    Text, JSON and XML are answers code reads, and reads again — an error
    message quoted into an exception, a document parsed after being logged.
    Anything else is a payload: keeping it means holding all of it for a second
    read nobody asked for.

    Args:
        headers: The response's headers, keyed by lowered name.
    """
    values = headers.get("content-type")
    if not values:
        return False

    content_type = values[0].split(";")[0]
    return bool(content_type) and _WORTH_REREADING.search(content_type) is not None


def _entries(
    headers: Mapping[str, object] | Sequence[object],
) -> Iterator[tuple[str, Sequence[object]]]:
    if isinstance(headers, Mapping):
        for name, values in headers.items():
            yield name, _values(name, values)
        return

    for position, line in enumerate(headers):
        if not isinstance(line, str):
            raise InvalidArgumentError(
                f'Invalid value for header "{position}": expected string, '
                f'"{debug_type(line)}" given.'
            )
        name, _, value = line.partition(":")
        yield name, [value.lstrip()]


def _values(name: str, values: object) -> Sequence[object]:
    if isinstance(values, str):
        return [values]
    if values is None:
        return []
    if isinstance(values, Iterable):
        return list(values)
    if isinstance(values, int | float):
        return [values]

    raise InvalidArgumentError(
        f'Invalid value for header "{name}": expected string, "{debug_type(values)}" given.'
    )
