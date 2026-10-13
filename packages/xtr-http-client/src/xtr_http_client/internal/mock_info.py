"""What a scripted transfer knows about itself, once a client has issued it."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Final

from .mock_head import header_lines

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface

__all__ = ["issued_info"]

# The entries the client fills in, whatever the script says: a script cannot
# know the method, the URL or the options it is going to answer, and the rest
# are what sending it made true. Everything else a script wrote is carried
# through untouched, which is how a test puts an entry of its own on a
# response.
_FILLED_IN: Final = frozenset(
    {
        "canceled",
        "error",
        "http_code",
        "http_method",
        "redirect_count",
        "redirect_url",
        "response_headers",
        "start_time",
        "total_time",
        "url",
        "user_data",
    }
)


def issued_info(
    script: Mapping[str, object],
    message: ResponseInterface,
    method: str,
    url: str,
    options: Mapping[str, object],
) -> dict[str, object]:
    """The record of a scripted transfer, as it stands the moment it is handed back.

    Args:
        script: What the response was written with, whose entries outside the
            ones filled in here are kept as they were given.
        message: The status line and headers the answer arrives with.
        method: The method the request was made with.
        url: The URL it was made to, resolved.
        options: The options it was made with, merged.

    Returns:
        Every entry a caller can read off the response.
    """
    given_start = _reading(script.get("start_time"))
    start_time = time.time() if given_start is None else given_start
    lines = header_lines(message)
    total_time = _reading(script.get("total_time"))

    return {
        **{name: value for name, value in script.items() if name not in _FILLED_IN},
        "canceled": False,
        "error": None,
        "http_code": message.get_status_code(),
        "http_method": method,
        # Nothing is followed: a script answers the request that was made.
        "redirect_count": 0,
        "redirect_url": None,
        "response_headers": lines,
        "start_time": start_time,
        "total_time": total_time if total_time is not None else time.time() - start_time,
        "url": url,
        "user_data": options.get("user_data"),
    }


def _reading(value: object) -> float | None:
    """A clock reading the script gave, or ``None`` when it gave none."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    return float(value)
