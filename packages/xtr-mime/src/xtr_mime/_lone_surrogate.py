"""Finds what a byte that failed to decode leaves in a str: a lone surrogate.

Decoded with ``surrogateescape``, a byte that is not UTF-8 survives as a surrogate code point
with no partner. It is not text, so a name holding one is refused rather than written — the
email package of some Python versions cannot even write one in a quoted name.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["LONE_SURROGATE"]

# In a str every surrogate is alone: a character outside the BMP is one code point there.
LONE_SURROGATE: Final = re.compile(r"[\ud800-\udfff]")
