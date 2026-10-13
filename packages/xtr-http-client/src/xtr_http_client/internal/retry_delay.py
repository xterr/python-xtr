"""How long the server itself said to wait before asking again."""

from __future__ import annotations

import time
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

__all__ = ["retry_after_ms"]


def retry_after_ms(response: ResponseInterface) -> int | None:
    """The wait a ``Retry-After`` header asks for, in milliseconds.

    The header comes in two shapes — a number of seconds, or the date the
    answer will be worth asking for again — and both are read, because which
    one a server sends is the server's business. A date already past asks for
    no wait at all rather than a negative one.

    Args:
        response: The answer that may be asking to be asked again later.

    Returns:
        The wait in milliseconds, or ``None`` when the header is absent or is
        neither a number nor a date, which leaves the wait to the strategy.
    """
    after = response.get_header("retry-after")
    if not after:
        return None

    value = after[0].strip()
    try:
        return int(float(value) * 1000)
    except (OverflowError, ValueError):
        pass

    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None

    return max(0, int(when.timestamp() - time.time())) * 1000
