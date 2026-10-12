"""How much of an identifier a reading of a stored model may show."""

from __future__ import annotations

from typing import Final

__all__ = ["short_identifier"]

#: Eight characters are enough to tell two stored tokens apart in a log line
#: and far too few to be worth anything to whoever reads that log.
_SHOWN: Final[int] = 8


def short_identifier(identifier: str) -> str:
    """Return the start of ``identifier``, marked when there was more of it."""
    if len(identifier) <= _SHOWN:
        return identifier

    return f"{identifier[:_SHOWN]}..."
