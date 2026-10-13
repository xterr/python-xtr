"""The head of a scripted answer, read out of the info a script was written with.

A scripted response is written as a body and a mapping of what the transfer is
to claim about itself. The status line, the protocol version and the headers
are all in that mapping, under one entry and in any of three shapes, so reading
them out is one decision made here rather than at each place that needs one of
them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Final, cast

from xtr_http_message import Response

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

__all__ = ["header_lines", "response_header_lines", "scripted_message"]

# "HTTP/1.1 404 Not Found": what a hop begins with, and the one line in the
# headers that is not a header.
_STATUS_LINE: Final = re.compile(r"^HTTP/(\d+(?:\.\d+)?) (\d{3})(?: (.*))?$")

_DEFAULT_STATUS: Final = 200
_DEFAULT_VERSION: Final = "1.1"


def scripted_message(info: Mapping[str, object], length: int | None) -> Response:
    """The status line and headers a scripted answer arrives with.

    Args:
        info: What the script says the transfer claims about itself.
            ``http_code`` is the status, and ``response_headers`` the headers —
            which a status line among them overrides, since a line the script
            wrote out says the version and the reason phrase as well.
        length: The real length of the body, when the body is one that has a
            length. ``Content-Length`` is then set to it, so a script that
            claims a length its body does not have cannot leave a reader
            waiting for bytes that are never coming. ``None`` — a body
            produced piece by piece — leaves whatever was claimed.

    Returns:
        The message the answer is read from.
    """
    status = _status(info.get("http_code"))
    version = _DEFAULT_VERSION
    reason: str | None = None
    headers: dict[str, list[str]] = {}

    for line in response_header_lines(info.get("response_headers")):
        hop = _STATUS_LINE.match(line)
        if hop is not None:
            # No phrase at all (`None`) asked for the recommended one; an
            # empty phrase after the space asked for none, and gets none.
            version, status, reason = hop[1], int(hop[2]), hop[3]
            # A new hop answers for itself: the headers before it were the
            # previous one's.
            headers.clear()
            continue

        name, separator, value = line.partition(":")
        if separator:
            headers.setdefault(_first_cased(headers, name), []).append(value.lstrip())

    if length is not None:
        headers[_first_cased(headers, "Content-Length")] = [str(length)]

    return Response(status, headers, None, version, reason)


def response_header_lines(value: object) -> list[str]:
    """Headers written in any of the three shapes a script may write them, as lines.

    A mapping is the shape a header is named in; a sequence of lines is the
    shape a transfer reports, and the only one that can carry a status line;
    a single string is one of those lines on its own.

    Args:
        value: What the script gave for ``response_headers``.

    Returns:
        One line per value, each ``"Name: value"`` or a status line.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        mapping = cast("Mapping[object, object]", value)

        return [f"{name}: {one}" for name, values in mapping.items() for one in _each(values)]
    if isinstance(value, Iterable):
        return [str(line) for line in value]

    return []


def header_lines(message: ResponseInterface) -> list[str]:
    """The raw status and header lines a message would have arrived as.

    Args:
        message: The message the answer is read from.

    Returns:
        The status line, then one line per header value.
    """
    status_line = (
        f"HTTP/{message.get_protocol_version()} "
        f"{message.get_status_code()} {message.get_reason_phrase()}"
    )

    return [
        status_line,
        *(f"{name}: {value}" for name, values in message.get_headers().items() for value in values),
    ]


def _each(values: object) -> list[str]:
    """Every value given for one header name."""
    if isinstance(values, str):
        return [values]
    if isinstance(values, Sequence):
        return [str(one) for one in values]

    return [str(values)]


def _status(value: object) -> int:
    """The status the script claims, or the one an answer has when nobody said."""
    if isinstance(value, bool) or not isinstance(value, int):
        return _DEFAULT_STATUS

    return value


def _first_cased(headers: Mapping[str, list[str]], name: str) -> str:
    """The case a header name was first seen in, so a repeat does not split it."""
    wanted = name.lower()
    for seen in headers:
        if seen.lower() == wanted:
            return seen

    return name
