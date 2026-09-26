"""The errors the caching contract names.

:class:`CacheError` is the root every caching error derives from, including
every one an implementation adds, so catching it catches anything caching can
go wrong with, whichever package raised it. :class:`InvalidArgumentError` is
the one the interfaces here document raising.
"""

from __future__ import annotations

from .cache_error import CacheError
from .invalid_argument_error import InvalidArgumentError

__all__ = [
    "CacheError",
    "InvalidArgumentError",
]
